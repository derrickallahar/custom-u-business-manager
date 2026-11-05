"""Validate payment records and replay every invoice balance from its audit trail."""
from datetime import date,datetime
from collections import Counter
import re,uuid
from quote_rules import need,text
METHODS={'cash':'Cash','bank_transfer':'Bank transfer','card':'Card','cheque':'Cheque','other':'Other'}
FIELDS={'id','serial','invoice_id','invoice_version','is_test','number','details','balance_before_cents','balance_after_cents','status','version','created_by','created_at','reversed_by','reversed_at','reversal_reason'}
def ident(v):
    need(isinstance(v,str));need(str(uuid.UUID(v))==v)
def timestamp(v):
    need(isinstance(v,str));d=datetime.fromisoformat(v.replace('Z','+00:00'));need(d.tzinfo is not None);return d
def integer(v,lo=0,hi=100000000000):need(type(v) is int and lo<=v<=hi)
def payment_record(r,inv):
    need(isinstance(r,dict) and set(r)==FIELDS);ident(r['id']);ident(r['invoice_id']);ident(r['created_by'])
    need(inv['status']=='issued' and r['invoice_id']==inv['id'] and type(r['is_test']) is bool and r['is_test']==inv['is_test'])
    need(type(r['invoice_version']) is int and r['invoice_version']==inv['version'])
    integer(r['serial'],1,99999999);need(r['number']==('CU-TEST-R-' if r['is_test'] else 'CU-R-')+str(r['serial']).zfill(8))
    d=r['details'];need(isinstance(d,dict) and set(d)=={'payment_date','amount_cents','method','reference','note'})
    need(isinstance(d['payment_date'],str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}',d['payment_date']) is not None);date.fromisoformat(d['payment_date'])
    integer(d['amount_cents'],1);need(d['method'] in METHODS)
    need(text(d['reference'],120,False)==d['reference'] and text(d['note'],1000,True)==d['note'])
    total=inv['quote_snapshot']['data']['total_cents']
    integer(r['balance_before_cents'],0,total);integer(r['balance_after_cents'],0,total)
    need(r['balance_before_cents']-d['amount_cents']==r['balance_after_cents'])
    created=timestamp(r['created_at']);integer(r['version'],1,2)
    if r['status']=='recorded':need(r['version']==1 and r['reversed_by'] is None and r['reversed_at'] is None and r['reversal_reason']=='')
    else:
        need(r['status']=='reversed' and r['version']==2);ident(r['reversed_by']);need(timestamp(r['reversed_at'])>=created)
        need(bool(r['reversal_reason']) and text(r['reversal_reason'],500,True)==r['reversal_reason'])
    return r

def validate_payments(obj):
    invoices={i['id']:i for i in obj['invoices']};payments=obj['payments'];audit=obj['payment_audit']
    need(isinstance(payments,list) and len(payments)<=20000 and isinstance(audit,list) and len(audit)<=40000)
    records={};numbers=set();counts=Counter()
    for r in payments:
        need(isinstance(r,dict) and r.get('invoice_id') in invoices);payment_record(r,invoices[r['invoice_id']]);need(r['id'] not in records and r['number'] not in numbers)
        records[r['id']]=r;numbers.add(r['number']);counts[r['invoice_id']]+=1
    need(all(n<=500 for n in counts.values()))
    balances={i['id']:i['quote_snapshot']['data']['total_cents'] for i in obj['invoices']};versions=Counter();latest={};seen=set()
    for a in sorted(audit,key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        need(isinstance(a,dict) and set(a)=={'id','payment_id','invoice_id','ledger_version','operation','actor_id','happened_at','before_record','after_record','balance_before_cents','balance_after_cents'})
        integer(a['id'],1,9007199254740991);need(a['id'] not in seen);seen.add(a['id']);ident(a['actor_id']);timestamp(a['happened_at'])
        pid=a['payment_id'];iid=a['invoice_id'];need(pid in records and iid==records[pid]['invoice_id'])
        before=a['before_record'];after=a['after_record'];need(before==latest.get(pid));payment_record(after,invoices[iid]);need(after['id']==pid)
        integer(a['ledger_version'],1,1000);need(a['ledger_version']==versions[iid]+1);versions[iid]+=1
        integer(a['balance_before_cents']);integer(a['balance_after_cents']);need(a['balance_before_cents']==balances[iid])
        amount=after['details']['amount_cents']
        if a['operation']=='record':
            need(before is None and after['status']=='recorded' and after['created_by']==a['actor_id'] and timestamp(after['created_at'])==timestamp(a['happened_at']))
            need(after['balance_before_cents']==a['balance_before_cents'] and after['balance_after_cents']==a['balance_after_cents']);balances[iid]-=amount
        else:
            need(a['operation']=='reverse' and before is not None and before['status']=='recorded' and after['status']=='reversed')
            need(after['reversed_by']==a['actor_id'] and timestamp(after['reversed_at'])==timestamp(a['happened_at']))
            mutable={'status','version','reversed_by','reversed_at','reversal_reason'}
            need({k:v for k,v in before.items() if k not in mutable}=={k:v for k,v in after.items() if k not in mutable});balances[iid]+=amount
        need(0<=balances[iid]<=invoices[iid]['quote_snapshot']['data']['total_cents'] and balances[iid]==a['balance_after_cents']);latest[pid]=after
    need(latest==records)
    for iid,i in invoices.items():need(balances[iid]==i['quote_snapshot']['data']['total_cents']-sum(p['details']['amount_cents'] for p in payments if p['invoice_id']==iid and p['status']=='recorded'))
    return obj
