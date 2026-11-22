"""Strict administrator-control backup validation with complete audit replay."""
import ipaddress,re
from datetime import datetime
from decimal import Decimal
from uuid import UUID


def need(ok):
    if not ok:raise ValueError('INVALID_ADMIN_CONTROLS')


def uid(value):
    need(isinstance(value,str) and str(UUID(value))==value)


def stamp(value):
    need(isinstance(value,str));d=datetime.fromisoformat(value.replace('Z','+00:00'));need(d.tzinfo is not None);return d


def number_ok(number,serial,kind,test=False):
    old=('CU-Q-' if kind=='quote' else 'CU-TEST-I-' if test else 'CU-I-')+str(serial).zfill(8)
    return number==old or not test and isinstance(number,str) and re.fullmatch(r'[1-9][0-9]{0,7}',number) is not None


def control(row):
    need(isinstance(row,dict) and set(row)=={'key','kind','data','version','created_at','updated_at'})
    need(type(row['version']) is int and row['version']>0);need(stamp(row['updated_at'])>=stamp(row['created_at']))
    key,kind,d=row['key'],row['kind'],row['data'];need(isinstance(d,dict));need(isinstance(key,str))
    if kind=='policy':
        need(key=='policy' and set(d)=={'enabled','gateway_hash'} and type(d['enabled']) is bool)
        need(isinstance(d['gateway_hash'],str) and (d['gateway_hash']=='' or bool(re.fullmatch('[a-f0-9]{64}',d['gateway_hash']))));need(not d['enabled'] or bool(d['gateway_hash']))
    elif kind=='numbering':
        need(key=='numbering' and set(d)=={'quote_next','invoice_next'})
        need(all(type(v) is int and 1<=v<=100000000 for v in d.values()))
    elif kind=='network':
        need(key.startswith('network:'));uid(key[8:]);need(set(d)=={'label','cidr','active'} and type(d['active']) is bool)
        need(isinstance(d['label'],str) and 1<=len(d['label'].strip())<=100)
        network=ipaddress.ip_network(d['cidr'],strict=True);need(network.prefixlen>=(24 if network.version==4 else 48));need(str(network)==d['cidr'])
    elif kind=='grant':
        need(set(d)=={'employee_id','active','starts_at','ends_at','reason'});uid(d['employee_id']);need(key=='grant:'+d['employee_id'] and type(d['active']) is bool)
        start=stamp(d['starts_at']);need(d['ends_at'] is None or stamp(d['ends_at'])>start)
        need(isinstance(d['reason'],str) and 1<=len(d['reason'])<=500)
    elif kind=='discount':
        need(set(d)=={'customer_id','percent','note'});uid(d['customer_id']);need(key=='discount:'+d['customer_id'])
        need(isinstance(d['percent'],str) and bool(re.fullmatch(r'[0-9]{1,3}\.[0-9]{2}',d['percent'])) and Decimal(d['percent'])<=100)
        need(isinstance(d['note'],str) and len(d['note'])<=500)
    else:need(False)
    return row


def validate_admin_controls(snapshot):
    block=snapshot.get('admin_controls');need(isinstance(block,dict) and set(block)=={'records','audit'})
    need(isinstance(block['records'],list) and isinstance(block['audit'],list));records={}
    for row in block['records']:
        control(row);need(row['key'] not in records);records[row['key']]=row
    need({'policy','numbering'}<=set(records));latest={};seen=set()
    for a in sorted(block['audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        need(isinstance(a,dict) and set(a)=={'id','record_key','actor_id','happened_at','before_record','after_record'})
        need(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id'])
        key=a['record_key'];before=a['before_record'];after=control(a['after_record']);need(key==after['key'] and key in records);need(before==latest.get(key))
        need(stamp(a['happened_at'])==stamp(after['updated_at']))
        if a['actor_id'] is None:need(before is None and key in ('policy','numbering'))
        else:uid(a['actor_id'])
        if before is None:need(after['version']==1 and after['created_at']==after['updated_at'])
        else:
            need(after['version']==before['version']+1 and after['created_at']==before['created_at'] and after['kind']==before['kind'] and stamp(after['updated_at'])>=stamp(before['updated_at']))
            need(after['data']!=before['data'])
            if after['kind']=='numbering':need(all(after['data'][k]>=before['data'][k] for k in ('quote_next','invoice_next')))
        latest[key]=after
    need(latest==records)
    for collection,key in [('quotes','quote_next'),('invoices','invoice_next')]:
        for doc in snapshot.get(collection,[]):
            if not doc.get('is_test') and re.fullmatch(r'[1-9][0-9]{0,7}',doc['number']):need(int(doc['number'])<records['numbering']['data'][key])
    return block
