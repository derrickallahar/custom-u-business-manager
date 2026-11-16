"""ShopVox receivables rehearsals. Never manufacture sales or payment transactions."""
import base64
import csv
import hashlib
import io
import json
import re
from datetime import date
from decimal import Decimal

MAX_CSV = 1_000_000
MAX_ROWS = 1000
FIELDS = ('IN#', 'Customer', 'Invoice Date', 'Due Date', 'Invoice Total', 'Payments', 'Credit', 'Balance', 'Status')
MONEY = {'Invoice Total': 'total_cents', 'Payments': 'paid_cents', 'Credit': 'credit_cents', 'Balance': 'balance_cents'}
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')

def need(ok, code='OPENING_DATA_INVALID'):
    if not ok: raise ValueError(code)

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()

def text(value, limit, blank=False):
    need(isinstance(value, str) and (blank or bool(value.strip())) and len(value) <= limit and not any(ord(c)<32 or ord(c)==127 for c in value))
    return value.strip()

def day(value):
    need(isinstance(value, str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value) is not None, 'OPENING_DATE_INVALID')
    try: result = date.fromisoformat(value)
    except ValueError: raise ValueError('OPENING_DATE_INVALID') from None
    return result

def parse_source(encoded, as_of):
    cutoff = day(as_of)
    need(isinstance(encoded, str) and len(encoded) <= 4*((MAX_CSV+2)//3), 'OPENING_FILE_TOO_LARGE')
    try:
        raw = base64.b64decode(encoded, validate=True)
        need(0 < len(raw) <= MAX_CSV, 'OPENING_FILE_TOO_LARGE')
        source = raw.decode('utf-8-sig')
    except (ValueError, UnicodeError) as e:
        if str(e).startswith('OPENING_'): raise
        raise ValueError('OPENING_CSV_INVALID') from None
    need('\x00' not in source, 'OPENING_CSV_INVALID')
    try:
        reader = csv.DictReader(io.StringIO(source, newline=''), strict=True)
        headers = reader.fieldnames
        need(isinstance(headers, list) and len(headers) == len(set(headers)) and len(headers) <= 100 and all(k in headers for k in FIELDS), 'OPENING_COLUMNS_REQUIRED')
        rows, seen = [], set()
        for index, r in enumerate(reader, 2):
            need(len(rows)<MAX_ROWS, 'OPENING_ROW_LIMIT')
            need(None not in r and all(v is not None for v in r.values()), 'OPENING_CSV_INVALID')
            number = text(r['IN#'], 60)
            need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 /_.-]{0,59}', number) is not None, 'OPENING_NUMBER_INVALID')
            need(number.casefold() not in seen, 'OPENING_DUPLICATE_INVOICE'); seen.add(number.casefold())
            invoice_date, due_date = day(r['Invoice Date']), day(r['Due Date'])
            need(invoice_date <= cutoff and due_date >= invoice_date, 'OPENING_DATE_INVALID')
            status = text(r['Status'], 40).lower()
            need(status in ('past_due','open','unpaid','partially_paid','partial','due','sent','issued','overdue'), 'OPENING_STATUS_INVALID')
            amounts = {}
            for source_key, key in MONEY.items():
                value = r[source_key].strip()
                need(re.fullmatch(r'(?:0|[1-9]\d{0,8})(?:\.\d{1,2})?', value) is not None, 'OPENING_AMOUNT_INVALID')
                amounts[key] = int(Decimal(value)*100)
            need(amounts['balance_cents']>0 and amounts['total_cents']-amounts['paid_cents']-amounts['credit_cents']==amounts['balance_cents'], 'OPENING_BALANCE_MISMATCH')
            rows.append({'source_row': index, 'number': number, 'source_customer': text(r['Customer'], 200), 'invoice_date': invoice_date.isoformat(), 'due_date': due_date.isoformat(), 'source_status': status, **amounts})
        need(rows, 'OPENING_NO_ROWS')
    except csv.Error: raise ValueError('OPENING_CSV_INVALID') from None
    return rows, hashlib.sha256(raw).hexdigest()

def checks(value):
    need(isinstance(value, dict) and set(value)=={'all_unpaid','currency','unapplied_review'}, 'OPENING_CHECKS_REQUIRED')
    need(type(value['all_unpaid']) is bool and value['currency']=='BSD' and value['unapplied_review'] in ('unconfirmed','none_confirmed','separate_review_required'), 'OPENING_CHECKS_REQUIRED')
    return dict(value)

def totals(rows):
    return {**{key:sum(r[key] for r in rows) for key in MONEY.values()}, 'invoice_count':len(rows), 'source_customer_count':len({r['source_customer'] for r in rows})}

def make_plan(encoded, as_of, source_name, review, customers, mappings):
    rows, source_sha256 = parse_source(encoded, as_of)
    source_name=text(source_name, 120)
    need('/' not in source_name and '\\' not in source_name, 'OPENING_FILE_NAME_INVALID')
    review=checks(review)
    need(isinstance(customers,list) and len(customers)<=5000 and isinstance(mappings,dict), 'OPENING_MAPPING_INVALID')
    by_id={r['id']:r for r in customers}
    names=sorted({r['source_customer'] for r in rows}, key=str.casefold)
    need(set(mappings)<=set(names), 'OPENING_MAPPING_INVALID')
    groups=[]; chosen={}
    norm=lambda s:' '.join(s.split()).casefold()
    for name in names:
        candidates=[r for r in customers if r['active'] is True and norm(r['name'])==norm(name)]
        manual=name in mappings
        ident=mappings.get(name) if manual else candidates[0]['id'] if len(candidates)==1 else None
        record=by_id.get(ident) if isinstance(ident,str) else None
        need(not manual or record is not None and record['active'] is True, 'OPENING_MAPPING_INVALID')
        if record:
            chosen[name]={'customer_id':record['id'],'customer_version':record['version'],'customer_name':record['name'],'match_method':'manual' if manual else 'exact_name'}
        groups.append({'source_customer':name,'invoice_count':sum(r['source_customer']==name for r in rows),'balance_cents':sum(r['balance_cents'] for r in rows if r['source_customer']==name),'customer_id':ident,'customer_name':record['name'] if record else '', 'match_method':chosen[name]['match_method'] if record else 'unmatched','candidate_count':len(candidates)})
    matched=[{**r,**chosen.get(r['source_customer'],{'customer_id':None,'customer_version':None,'customer_name':'','match_method':'unmatched'})} for r in rows]
    plan={'mode':'rehearsal','as_of':as_of,'source_name':source_name,'source_sha256':source_sha256,'csv_base64':encoded,'review':review,'rows':matched,'totals':totals(rows)}
    report={k:v for k,v in plan.items() if k!='csv_base64'}
    report.update(groups=groups,can_save=len(chosen)==len(names),unmatched_customers=len(names)-len(chosen),mapped_customer_count=len({r['customer_id'] for r in chosen.values()}))
    return plan,report

def validate_batch(batch, crm_ids=None):
    need(isinstance(batch,dict) and set(batch)=={'id','mode','as_of','source_name','source_sha256','csv_base64','review','rows','totals','plan_sha256','created_by','created_at'})
    need(UUID.fullmatch(batch['id']) is not None and UUID.fullmatch(batch['created_by']) is not None and batch['mode']=='rehearsal')
    from datetime import datetime
    need(datetime.fromisoformat(batch['created_at'].replace('Z','+00:00')).tzinfo is not None)
    checks(batch['review']); text(batch['source_name'],120)
    original,sha=parse_source(batch['csv_base64'],batch['as_of'])
    need(sha==batch['source_sha256'] and batch['totals']==totals(original) and len(batch['rows'])==len(original))
    groups={}
    for source, r in zip(original,batch['rows']):
        need(set(r)==set(source)|{'customer_id','customer_version','customer_name','match_method'} and all(r[k]==v for k,v in source.items()))
        need(UUID.fullmatch(r['customer_id']) is not None and type(r['customer_version']) is int and r['customer_version']>0 and r['match_method'] in ('exact_name','manual'))
        text(r['customer_name'],200)
        if crm_ids is not None: need(r['customer_id'] in crm_ids)
        match={k:r[k] for k in ('customer_id','customer_version','customer_name','match_method')}
        need(r['source_customer'] not in groups or groups[r['source_customer']]==match);groups[r['source_customer']]=match
    payload={k:batch[k] for k in ('mode','as_of','source_name','source_sha256','csv_base64','review','rows','totals')}
    need(digest(payload)==batch['plan_sha256'])
    return batch

def validate_opening(obj):
    batches=obj['opening_batches'];audit=obj['opening_audit']
    need(isinstance(batches,list) and len(batches)<=20 and isinstance(audit,list) and len(audit)==len(batches))
    crm={r['id'] for r in obj['crm']['records'] if r['kind']=='customer'}
    records={}; hashes=set()
    for r in batches:
        validate_batch(r,crm);need(r['id'] not in records and r['plan_sha256'] not in hashes)
        records[r['id']]=r;hashes.add(r['plan_sha256'])
    seen=set();events=set()
    for a in audit:
        need(isinstance(a,dict) and set(a)=={'id','batch_id','actor_id','happened_at','record_snapshot'})
        need(type(a['id']) is int and a['id']>0 and a['id'] not in events);events.add(a['id'])
        need(a['batch_id'] in records and a['batch_id'] not in seen);seen.add(a['batch_id']);r=records[a['batch_id']]
        need(a['actor_id']==r['created_by'] and a['happened_at']==r['created_at'] and a['record_snapshot']=={k:v for k,v in r.items() if k!='csv_base64'})
    need(seen==set(records))
