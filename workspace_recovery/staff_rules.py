"""Offline validation of staff access settings; never creates cloud logins."""
from recover_crm import require,uid,date
KEYS={'customers.view','customers.create','customers.edit','quotes.view','quotes.create','quotes.edit','quotes.amend','quotes.approve','quotes.send','invoices.view','invoices.create','invoices.edit','invoices.amend','invoices.issue','invoices.send','payments.view','payments.record','payments.reverse','jobs.view','jobs.create','jobs.edit','jobs.progress','artwork.view','artwork.upload','artwork.approve','products.view','products.create','products.edit','products.send'}

def record(r):
    require(isinstance(r,dict) and set(r)=={'user_id','registered_email','active','permissions','version','created_at','updated_at'})
    uid(r['user_id']);require(type(r['active']) is bool and type(r['version']) is int and 1<=r['version']<1000000000)
    require(isinstance(r['registered_email'],str) and 3<=len(r['registered_email'])<=254 and '@' in r['registered_email'])
    require(date(r['updated_at'])>=date(r['created_at']))
    p=r['permissions'];require(isinstance(p,dict) and set(p)<=KEYS and all(type(v) is bool for v in p.values()))
    for k,v in p.items():
        if v:require(p.get(k.split('.')[0]+'.view') is True)
    if p.get('quotes.create') or p.get('quotes.edit'):require(p.get('customers.view') is True)
    if p.get('artwork.view'):require(p.get('jobs.view') is True)
    if p.get('jobs.create'):require(p.get('quotes.view') is True)
    if p.get('payments.view'):require(p.get('invoices.view') is True)

def validate_staff(obj):
    require(type(obj['staff_enabled']) is bool)
    require(isinstance(obj['staff_access'],list) and len(obj['staff_access'])<=100)
    require(isinstance(obj['staff_members'],list) and len(obj['staff_members'])<=1000)
    require(isinstance(obj['staff_audit'],list) and len(obj['staff_audit'])<=100000)
    members={}
    for m in obj['staff_members']:
        require(isinstance(m,dict) and set(m)=={'user_id','role','active','created_at'})
        uid(m['user_id']);date(m['created_at']);require(m['user_id'] not in members and m['role'] in ('admin','sales','office','production') and type(m['active']) is bool)
        members[m['user_id']]=m
    records={}
    for r in obj['staff_access']:
        record(r);require(r['user_id'] in members and r['user_id'] not in records);records[r['user_id']]=r
    seen=set();latest={}
    for a in sorted(obj['staff_audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','user_id','actor_id','happened_at','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id'])
        uid(a['user_id']);uid(a['actor_id']);date(a['happened_at']);require(a['actor_id'] in members)
        before=a['before_record'];after=a['after_record'];record(after)
        require(after['user_id']==a['user_id'] and before==latest.get(a['user_id']))
        if before is None:require(after['version']==1 and not after['active'] and after['permissions']=={})
        else:
            require(after['version']==before['version']+1 and after['created_at']==before['created_at'] and after['registered_email']==before['registered_email'] and date(after['updated_at'])>=date(before['updated_at']))
        latest[a['user_id']]=after
    require(latest==records)
