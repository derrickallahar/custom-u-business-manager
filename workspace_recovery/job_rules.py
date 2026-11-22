"""Validate complete job records and their immutable version history offline."""
from datetime import date as day
from recover_crm import require,uid,date
STAGES={'planning','in_production','ready','completed','on_hold','cancelled'}
DETAILS={'due_date','assigned_to','priority','instructions','customer_approved','customer_reference','artwork_approved','artwork_reference'}
def details(d):
    require(isinstance(d,dict) and set(d)==DETAILS)
    for k in DETAILS-{'customer_approved','artwork_approved'}:
        v=d[k];require(isinstance(v,str) and v==v.strip(' \n\r\t') and len(v)<=({'instructions':4000,'assigned_to':160}.get(k,500)) and all((ord(c)>=32 and ord(c)!=127) or c in '\n\r\t' for c in v))
    require(d['priority'] in ('normal','urgent'))
    if d['due_date']:
        v=day.fromisoformat(d['due_date']);require(2000<=v.year<=2100 and v.isoformat()==d['due_date'])
    for k in ('customer','artwork'):
        require(type(d[k+'_approved']) is bool)
        if d[k+'_approved']:require(len(d[k+'_reference'])>=3)

def source(q):
    return {'quote_number':q['number'],'quote_version':q['version'],'customer_id':q['customer_id'],'customer_name':q['customer_snapshot']['name'],'contact_name':(q['contact_snapshot'] or {}).get('name',''),'title':q['data']['title'],'lines':[{k:l[k] for k in ('description','quantity','unit','finish','placement')} for l in q['data']['lines']]}

def transition(before,after,op):
    a=before['status'];b=after['status']
    if op=='reopen':return a in ('completed','cancelled') and b=='planning'
    return a not in ('completed','cancelled') and a!=b and (b in ('on_hold','cancelled') or (a,b) in {('on_hold','planning'),('planning','in_production'),('in_production','ready'),('ready','completed')})

def validate_jobs(obj,allow_artwork=False):
    require(isinstance(obj['jobs'],list) and len(obj['jobs'])<=10000 and isinstance(obj['job_audit'],list) and len(obj['job_audit'])<=100000)
    quotes={q['id']:q for q in obj['quotes']};invoices={i['id']:i for i in obj['invoices']};members={m['user_id']:m for m in obj['staff_members']}
    fields={'id','serial','number','is_test','quote_id','source','details','status','version','last_reason','release_check','created_by','created_at','updated_at'}
    def record(r):
        require(isinstance(r,dict) and set(r)==fields);uid(r['id']);uid(r['quote_id']);uid(r['created_by']);require(r['created_by'] in members)
        require(type(r['serial']) is int and 1<=r['serial']<=99999999 and type(r['version']) is int and 1<=r['version']<=999999999 and type(r['is_test']) is bool)
        require(r['number']==('CU-TEST-J-' if r['is_test'] else 'CU-J-')+str(r['serial']).zfill(8) and r['status'] in STAGES)
        require(date(r['updated_at'])>=date(r['created_at']));q=quotes[r['quote_id']];require(q['status']=='issued' and r['source']==source(q));details(r['details'])
        require(isinstance(r['last_reason'],str) and len(r['last_reason'])<=500 and r['last_reason']==r['last_reason'].strip() and all(ord(c)>=32 for c in r['last_reason']))
        g=r['release_check']
        if g is not None:
            require(isinstance(g,dict) and set(g) in ({'ready','code','invoice_id','checked_at','actor_id'},{'ready','code','invoice_id','checked_at','actor_id','artwork_file_id','artwork_revision'}) and g['ready'] is True and g['code']=='READY');uid(g['actor_id']);require(g['actor_id'] in members)
            if 'artwork_file_id' in g:require(allow_artwork);uid(g['artwork_file_id']);require(type(g['artwork_revision']) is int and g['artwork_revision']>0)
            require(date(r['created_at'])<=date(g['checked_at'])<=date(r['updated_at']))
            if g['invoice_id'] is not None:
                uid(g['invoice_id']);i=invoices[g['invoice_id']];require(i['quote_id']==r['quote_id'] and i['is_test']==r['is_test'])
            if q['data']['deposit_cents']>0:require(g['invoice_id'] is not None)
        if r['status'] in ('in_production','ready','completed'):require(g is not None)
    records={};numbers=set();pairs=set()
    for r in obj['jobs']:
        record(r);pair=(r['quote_id'],r['is_test']);require(r['id'] not in records and r['number'] not in numbers and pair not in pairs);records[r['id']]=r;numbers.add(r['number']);pairs.add(pair)
    latest={};seen=set()
    for a in sorted(obj['job_audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','job_id','actor_id','happened_at','operation','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id']);uid(a['job_id']);require(a['actor_id'] in members);date(a['happened_at'])
        b=a['before_record'];r=a['after_record'];record(r);require(a['job_id'] in records and r['id']==a['job_id'] and b==latest.get(a['job_id']) and a['happened_at']==r['updated_at'])
        if b is None:
            require(a['operation']=='create' and r['version']==1 and r['status']=='planning' and r['release_check'] is None and r['last_reason']=='' and r['created_by']==a['actor_id'] and r['created_at']==r['updated_at'])
            require(r['details']==dict(due_date='',assigned_to='',priority='normal',instructions='',customer_approved=False,customer_reference='',artwork_approved=False,artwork_reference=''))
        else:
            require(r['version']==b['version']+1 and date(r['updated_at'])>=date(b['updated_at']))
            op=a['operation'];require(op in ('save','transition','reopen'))
            mutable={'version','updated_at','last_reason'}
            if op=='save':
                mutable.add('details');require(b['status'] not in ('completed','cancelled') and r['last_reason']=='')
            else:
                mutable|={'status','release_check'};require(transition(b,r,op) and len(r['last_reason'])>=3)
                if r['status'] in ('in_production','ready','completed'):
                    require(r['details']['customer_approved'] and r['details']['artwork_approved'])
                    require(r['release_check']['checked_at']==r['updated_at'] and r['release_check']['actor_id']==a['actor_id'])
                else:require(r['release_check']==b['release_check'])
            require({k:v for k,v in b.items() if k not in mutable}=={k:v for k,v in r.items() if k not in mutable})
        latest[a['job_id']]=r
    require(latest==records)
