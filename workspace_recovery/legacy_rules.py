"""Imported balances and immutable servicing events; no new VAT documents or money movement."""
from datetime import datetime
from zoneinfo import ZoneInfo
from opening_rules import need, text, day, UUID, validate_batch

BOOK_KEYS={'id','mode','source_id','plan_sha256','as_of','review_note','created_by','created_at'}
EVENT_KEYS={'id','entry_id','kind','amount_cents','effective_date','reference','reason','reverses_id','created_by','created_at','version','request'}
COMMAND_KEYS={'op','id','mode','entry_id','amount_cents','effective_date','reference','reason','reverses_id','expected_version','confirmed'}

def uid(v):
    need(isinstance(v,str) and UUID.fullmatch(v) is not None,'LEGACY_DATA_INVALID')

def stamp(v):
    need(isinstance(v,str),'LEGACY_DATA_INVALID');d=datetime.fromisoformat(v.replace('Z','+00:00'));need(d.tzinfo is not None,'LEGACY_DATA_INVALID');return d

def cents(v,positive=False):
    need(type(v) is int and (1 if positive else 0)<=v<=99999999999,'LEGACY_AMOUNT_INVALID');return v

def clean(v,n,minimum=1):
    need(text(v,n)==v and len(v)>=minimum,'LEGACY_DATA_INVALID');return v

def validate_state(state):
    need(isinstance(state,dict) and set(state)=={'mode','book','source','entries','events'},'LEGACY_DATA_INVALID')
    need(state['mode'] in ('test','live') and isinstance(state['entries'],list) and len(state['entries'])<=1000 and isinstance(state['events'],list) and len(state['events'])<=5000,'LEGACY_DATA_INVALID')
    book=state['book'];entries=state['entries'];events=state['events']
    if book is None:
        need(state['source'] is None and not entries and not events,'LEGACY_DATA_INVALID');return []
    need(isinstance(book,dict) and set(book)==BOOK_KEYS,'LEGACY_DATA_INVALID')
    for k in ('id','source_id','created_by'):uid(book[k])
    made=stamp(book['created_at']);clean(book['review_note'],500,10);day(book['as_of'])
    source=validate_batch(state['source'])
    need(book['mode']==state['mode'] and book['source_id']==source['id'] and book['plan_sha256']==source['plan_sha256'] and book['as_of']==source['as_of'],'LEGACY_SOURCE_CHANGED')
    need(made>=stamp(source['created_at']),'LEGACY_DATA_INVALID')
    if book['mode']=='live':
        need(source['review']['all_unpaid'] is True and source['review']['unapplied_review']=='none_confirmed','LEGACY_FINAL_REVIEW_REQUIRED')
        age=(made.astimezone(ZoneInfo('America/Nassau')).date()-day(book['as_of'])).days;need(0<=age<=7,'LEGACY_FINAL_REVIEW_REQUIRED')
    originals={r['number'].casefold():r for r in source['rows']};by_id={};seen=set()
    need(len(entries)==len(originals),'LEGACY_DATA_INVALID')
    for r in entries:
        need(isinstance(r,dict),'LEGACY_DATA_INVALID');uid(r['id']);uid(r['book_id'])
        key=r['number'].casefold();original=originals.get(key)
        need(original is not None and key not in seen and r['id'] not in by_id and r['book_id']==book['id'] and r['mode']==book['mode'],'LEGACY_DATA_INVALID')
        need({k:v for k,v in r.items() if k not in ('id','book_id','mode')}==original,'LEGACY_SOURCE_CHANGED')
        seen.add(key);by_id[r['id']]=r
    event_ids=set();groups={i:[] for i in by_id}
    for e in events:
        need(isinstance(e,dict) and set(e)==EVENT_KEYS,'LEGACY_DATA_INVALID')
        for k in ('id','entry_id','created_by'):uid(e[k])
        need(e['id'] not in event_ids and e['id']!=book['id'] and e['entry_id'] in by_id,'LEGACY_DATA_INVALID');event_ids.add(e['id'])
        need(e['kind'] in ('payment','credit','reversal') and type(e['version']) is int and e['version']>=1,'LEGACY_DATA_INVALID');cents(e['amount_cents'],True)
        moment=stamp(e['created_at']);need(moment>=made,'LEGACY_DATA_INVALID')
        need(day(book['as_of'])<=day(e['effective_date'])<=moment.astimezone(ZoneInfo('America/Nassau')).date(),'LEGACY_DATE_OUTSIDE_PERIOD')
        clean(e['reference'],120);clean(e['reason'],500,3)
        command=e['request'];need(isinstance(command,dict) and set(command)==COMMAND_KEYS,'LEGACY_DATA_INVALID')
        need(command['confirmed'] is True and type(command['amount_cents']) is int and type(command['expected_version']) is int and command['expected_version']==e['version']-1 and command['mode']==book['mode'] and command['op']==e['kind'],'LEGACY_DATA_INVALID')
        for k in ('id','entry_id','amount_cents','effective_date','reference','reason','reverses_id'):need(command[k]==e[k],'LEGACY_DATA_INVALID')
        groups[e['entry_id']].append(e)
    result=[]
    for ident,r in by_id.items():
        group=sorted(groups[ident],key=lambda e:e['version']);balance=r['balance_cents'];active={};previous=made
        for index,e in enumerate(group,1):
            need(e['version']==index and stamp(e['created_at'])>=previous,'LEGACY_DATA_INVALID');previous=stamp(e['created_at'])
            if e['kind']=='reversal':
                uid(e['reverses_id']);target=active.pop(e['reverses_id'],None)
                need(target is not None and target['amount_cents']==e['amount_cents'] and day(e['effective_date'])>=day(target['effective_date']),'LEGACY_REVERSAL_INVALID');balance+=e['amount_cents']
            else:
                need(e['reverses_id'] is None and e['amount_cents']<=balance,'LEGACY_EXCEEDS_BALANCE')
                need(not any(x['kind']==e['kind'] and x['reference'].lower()==e['reference'].lower() for x in active.values()),'LEGACY_REFERENCE_ALREADY_USED')
                active[e['id']]=e;balance-=e['amount_cents']
        result.append({**r,'opening_cents':r['balance_cents'],'remaining_cents':balance,'version':len(group),'subsequent_paid_cents':sum(e['amount_cents'] for e in active.values() if e['kind']=='payment'),'subsequent_credit_cents':sum(e['amount_cents'] for e in active.values() if e['kind']=='credit'),'activity':[{**e,'reversed':e['kind']!='reversal' and e['id'] not in active} for e in group]})
    return sorted(result,key=lambda r:(r['customer_name'].casefold(),r['number']))

def view(state):
    rows=validate_state(state)
    return {'mode':state['mode'],'book':state['book'],'rows':rows,'totals':{k:sum(r[k] for r in rows) for k in ('opening_cents','subsequent_paid_cents','subsequent_credit_cents','remaining_cents')},'invoice_count':len(rows)}

def validate_legacy(obj):
    books=obj['legacy_books'];entries=obj['legacy_entries'];events=obj['legacy_events'];audit=obj['legacy_audit']
    need(all(isinstance(x,list) for x in (books,entries,events,audit)) and len(books)<=2 and len(entries)<=2000 and len(events)<=5000,'LEGACY_DATA_INVALID')
    sources={r['id']:r for r in obj['opening_batches']};modes=set();ids=set();expected={};used=set()
    for b in books:
        need(b['mode'] not in modes and b['id'] not in ids and b['id'] not in expected,'LEGACY_DATA_INVALID');modes.add(b['mode']);ids.add(b['id'])
        chosen=[r for r in entries if r['book_id']==b['id']];chosen_ids={r['id'] for r in chosen};need(not used&chosen_ids,'LEGACY_DATA_INVALID');used|=chosen_ids
        ev=[e for e in events if e['entry_id'] in chosen_ids]
        validate_state({'mode':b['mode'],'book':b,'source':sources.get(b['source_id']),'entries':chosen,'events':ev})
        expected[b['id']]=('import',b)
        for e in ev:
            need(e['id'] not in expected,'LEGACY_DATA_INVALID');expected[e['id']]=(e['kind'],e)
    need(used=={r['id'] for r in entries} and len(used)==len(entries) and all(e['entry_id'] in used for e in events),'LEGACY_DATA_INVALID')
    need(len(audit)==len(expected),'LEGACY_AUDIT_INVALID');seen=set();audit_ids=set()
    for a in audit:
        need(isinstance(a,dict) and set(a)=={'id','kind','record_id','actor_id','happened_at','record_snapshot'},'LEGACY_AUDIT_INVALID')
        need(type(a['id']) is int and a['id']>0 and a['id'] not in audit_ids and a['record_id'] not in seen and a['record_id'] in expected,'LEGACY_AUDIT_INVALID')
        kind,r=expected[a['record_id']];need(a['kind']==kind and a['actor_id']==r['created_by'] and a['happened_at']==r['created_at'] and a['record_snapshot']==r,'LEGACY_AUDIT_INVALID');seen.add(a['record_id']);audit_ids.add(a['id'])
