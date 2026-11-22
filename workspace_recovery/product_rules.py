"""Offline catalogue validation, including the complete per-product change chain."""
import re
from decimal import Decimal
from recover_crm import require, uid, date
from pricing_rules import pricing_valid

FIELDS={'code':40,'name':160,'category':80,'description':800,'unit':20,'finish':160,'placement':160,'unit_price':None,'vat_rate':None}

def product_record(r):
    require(isinstance(r,dict) and set(r)=={'id','data','active','version','created_at','updated_at'})
    uid(r['id']);require(type(r['active']) is bool and type(r['version']) is int and 1<=r['version']<=999999999)
    require(date(r['updated_at'])>=date(r['created_at']))
    d=r['data'];require(isinstance(d,dict) and set(d) in (set(FIELDS),set(FIELDS)|{'pricing'}))
    if 'pricing' in d:require(pricing_valid(d,r['active']))
    for k,limit in FIELDS.items():
        v=d[k];require(isinstance(v,str) and v==v.strip(' '))
        if limit is None:
            if 'pricing' in d and v=='':continue
            require(re.fullmatch(r'(0|[1-9][0-9]{0,6})\.[0-9]{2}',v) is not None)
            require(Decimal(v)<=Decimal(1000000 if k=='unit_price' else 100))
        else:
            require(len(v)<=limit and not re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',v))
            if k in ('code','name','unit'):require(bool(v))
            if k!='description':require(not re.search(r'[\x09\x0A\x0D]',v))
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,39}',d['code']) is not None)

def validate_products(obj):
    require(isinstance(obj['products'],list) and len(obj['products'])<=5000)
    require(isinstance(obj['product_audit'],list) and len(obj['product_audit'])<=100000)
    records={};codes=set()
    for r in obj['products']:
        product_record(r);require(r['id'] not in records and r['data']['code'].lower() not in codes)
        records[r['id']]=r;codes.add(r['data']['code'].lower())
    latest={};seen=set()
    for a in sorted(obj['product_audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','product_id','actor_id','happened_at','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id'])
        uid(a['actor_id']);date(a['happened_at']);require(a['product_id'] in records)
        before=a['before_record'];after=a['after_record'];require(before==latest.get(a['product_id']))
        product_record(after);require(after['id']==a['product_id'])
        if before is None:require(after['version']==1)
        else:require(after['version']==before['version']+1 and after['created_at']==before['created_at'] and date(after['updated_at'])>=date(before['updated_at']))
        latest[a['product_id']]=after
    require(latest==records)
