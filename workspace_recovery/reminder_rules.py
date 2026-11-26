"""Schedule decisions and strict offline validation of reminder history."""
from datetime import date,datetime
from zoneinfo import ZoneInfo
from html import escape
from email_delivery import address,identifier,checked_pdf,clean
from reminder_rules_112 import settings as settings112,invoice as invoice112
from reminder_text import DEFAULT_MESSAGES,validate_messages,stage_label

FIELDS={'enabled','days','repeat_days','send_hour','excluded_customers','excluded_invoices'}
NEW_FIELDS=FIELDS|{'credit_reminders','messages'}
SETTINGS=FIELDS|{'mode','version','updated_by','updated_at'}
INVOICE={'source','id','number','customer_id','customer_name','due_date','total_cents','balance_cents','customer_active','recipient'}
PACKET={'id','invoice','stage','recipient','sender','reply_to','subject','message','pdf_filename','pdf_sha256','pdf_base64'}
DELIVERY=PACKET|{'mode','settings_snapshot','sent_date','state','provider_id','error_code','actor_id','created_at','updated_at'}

def need(value):
    if not value:raise ValueError('REMINDER_DATA_INVALID')
def day(value):
    need(isinstance(value,str));result=date.fromisoformat(value);need(result.isoformat()==value);return result

def stamp(value):
    need(isinstance(value,str));result=datetime.fromisoformat(value.replace('Z','+00:00'));need(result.tzinfo is not None);return result

def defaults(mode):
    return {'mode':mode,'version':0,'enabled':False,'days':[3,7,14,30],'repeat_days':15,'send_hour':9,'excluded_customers':[],'excluded_invoices':[],'updated_by':None,'updated_at':None}

def upgraded(cfg):
    if 'messages' in cfg:return cfg
    return {**cfg,'enabled':False,'days':[d for d in cfg['days'] if d!=3] or [7,14,30],
            'credit_reminders':True,'messages':dict(DEFAULT_MESSAGES)}

def settings(value,full=True):
    if isinstance(value,dict) and 'messages' not in value:return settings112(value,full)
    need(isinstance(value,dict) and set(value)==(SETTINGS|{'credit_reminders','messages'} if full else NEW_FIELDS))
    base={k:v for k,v in value.items() if k not in ('credit_reminders','messages')}
    # New settings enter history only on an explicit user save (version >= 1).
    if full:need(type(value['version']) is int and value['version']>=1)
    settings112(base,full)
    need(type(value['credit_reminders']) is bool)
    validate_messages(value['messages']);return value

def credit_eligible(row,cfg):
    return bool(row and cfg.get('credit_reminders') and type(row.get('customer_terms_days')) is int and row['customer_terms_days']>0 and 'invoice_date' in row and (day(row['due_date'])-day(row['invoice_date'])).days==row['customer_terms_days'])

def stage_for(age,cfg,row=None):
    if age in (-15,0) and credit_eligible(row,cfg) and age>=-row['customer_terms_days']:return age
    due=[d for d in cfg['days'] if d<=age]
    if not due:return None
    last=max(cfg['days']);interval=cfg['repeat_days']
    return last+((age-last)//interval)*interval if interval and age>=last+interval else max(due)

def invoice(r):
    need(isinstance(r,dict))
    if 'invoice_date' in r:
        need(set(r)==INVOICE|{'invoice_date','customer_terms_days','customer_version'});day(r['invoice_date']);need(day(r['invoice_date'])<=day(r['due_date']))
        need(r['customer_terms_days'] is None or type(r['customer_terms_days']) is int and 0<=r['customer_terms_days']<=365)
        need(type(r['customer_version']) is int and r['customer_version']>0)
        invoice112({k:v for k,v in r.items() if k in INVOICE})
    else:invoice112(r)
    return r

def validate_reminders(obj):
    configs=obj['reminder_settings'];rows=obj['reminder_deliveries'];audits=obj['reminder_audit']
    need(isinstance(configs,list) and len(configs)==2 and {c['mode'] for c in configs}=={'test','live'})
    need(isinstance(rows,list) and len(rows)<=2000 and isinstance(audits,list) and len(audits)<=20000)
    expected={};used=set();dates=set();members={m['user_id'] for m in obj['staff_members']}
    from document_revisions import invoice_versions
    historic_invoices=invoice_versions(obj)
    sources={'native':{r['id']:r for r in obj['invoices']},'legacy':{r['id']:r for r in obj['legacy_entries']}}
    customer_versions={(a['after_record']['id'],a['after_record']['version']):a['after_record'] for a in obj['crm']['audit']}
    for cfg in configs:
        settings(cfg)
        if cfg['version']:expected['settings/'+cfg['mode']]=cfg;need(cfg['updated_by'] in members)
    for row in rows:
        need(isinstance(row,dict) and set(row)==DELIVERY);identifier(row['id']);identifier(row['actor_id']);need(row['actor_id'] in members)
        cfg=settings(row['settings_snapshot']);need(cfg['enabled'] and cfg['mode']==row['mode'] and cfg['updated_by']==row['actor_id'])
        r=invoice(row['invoice']);original=sources[r['source']].get(r['id']);need(original is not None and r['balance_cents']>0 and r['customer_active'])
        if r['source']=='native':
            original=next((i for (iid,version),i in historic_invoices.items() if iid==r['id'] and i['status']=='issued' and i['details']['due_date']==r['due_date'] and ('invoice_date' not in r or i['details']['invoice_date']==r['invoice_date'])),None)
            need(original is not None)
            need(original['is_test']==(row['mode']=='test') and original['number']==r['number'] and original['details']['due_date']==r['due_date'] and original['quote_snapshot']['customer_id']==r['customer_id'])
        else:need(original['mode']==row['mode'] and 'ShopVox '+original['number']==r['number'] and original['due_date']==r['due_date'] and original['customer_id']==r['customer_id'])
        if 'messages' in cfg:
            customer=customer_versions.get((r['customer_id'],r.get('customer_version')));need(customer is not None and customer['kind']=='customer' and customer['data'].get('payment_terms_days')==r['customer_terms_days'])
            need('invoice_date' in r and r['invoice_date']==(original['details']['invoice_date'] if r['source']=='native' else original['invoice_date']))
        age=(day(row['sent_date'])-day(r['due_date'])).days;need(type(row['stage']) is int and row['stage']==stage_for(age,cfg,r))
        need(day(row['sent_date'])==stamp(row['created_at']).astimezone(ZoneInfo('America/Nassau')).date() and stamp(row['updated_at'])>=stamp(row['created_at']))
        need(r['customer_id'] not in cfg['excluded_customers'] and r['source']+':'+r['id'] not in cfg['excluded_invoices'])
        for k in ('recipient','reply_to'):need(address(row[k])==row[k])
        address(r['recipient'])
        need(clean(row['sender'],300,True)==row['sender'] and clean(row['subject'],160,True)==row['subject'] and clean(row['message'],4000)==row['message'])
        if row['mode']=='test':need(row['subject'].startswith('TEST - ') and row['message'].startswith('TEST DELIVERY - '))
        else:need(row['recipient']==r['recipient'])
        need(row['pdf_filename']=='CustomU_Reminder_'+row['id']+'.pdf');checked_pdf(row)
        need(row['state'] in ('attempted','accepted','rejected','uncertain'))
        need((row['state']=='accepted')==(isinstance(row['provider_id'],str) and 1<=len(row['provider_id'])<=100))
        need((row['state'] in ('rejected','uncertain'))==(isinstance(row['error_code'],str) and 1<=len(row['error_code'])<=80))
        if row['state']!='accepted':need(row['provider_id'] is None)
        if row['state'] not in ('rejected','uncertain'):need(row['error_code'] is None)
        key=(row['mode'],r['source'],r['id'],row['stage']);daily=(row['mode'],r['source'],r['id'],row['sent_date']);need(key not in used and daily not in dates);used.add(key);dates.add(daily)
        record='delivery/'+row['id'];need(record not in expected);expected[record]={k:v for k,v in row.items() if k!='pdf_base64'}
    latest={};seen=set();versions={}
    for a in sorted(audits,key=lambda x:x['id']):
        need(set(a)=={'id','record_key','actor_id','happened_at','before_record','after_record'} and type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);identifier(a['actor_id']);stamp(a['happened_at'])
        key=a['record_key'];need(key in expected);before=a['before_record'];after=a['after_record']
        if key.startswith('settings/'):
            settings(after);need(key=='settings/'+after['mode']);versions[(after['mode'],after['version'])]=after;need(before==latest.get(key,defaults(after['mode'])) and after['version']==before['version']+1 and after['updated_by']==a['actor_id'] and after['updated_at']==a['happened_at'])
        else:
            need(before==latest.get(key) and after['id']==key.split('/')[1] and after['actor_id']==a['actor_id'] and after['updated_at']==a['happened_at'])
            if before is None:need(after['state']=='attempted' and after['created_at']==after['updated_at'] and after['provider_id'] is None and after['error_code'] is None)
            else:
                need(before['state']=='attempted' and after['state'] in ('accepted','rejected','uncertain'))
                mutable={'state','provider_id','error_code','updated_at'};need({k:v for k,v in before.items() if k not in mutable}=={k:v for k,v in after.items() if k not in mutable})
        latest[key]=after
    need(latest==expected)
    for row in rows:
        cfg=row['settings_snapshot'];need(versions.get((cfg['mode'],cfg['version']))==cfg)

def history_html(obj):
    esc=lambda x:escape(str(x))
    parts=['<!doctype html><meta charset="utf-8"><title>Custom U recovered reminders</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto}td,th{padding:10px;text-align:left;border-bottom:1px solid #ccc}h1{color:#b72030}</style><h1>Recovered reminder history</h1><p>Local recovery only. Opening this file does not schedule or send email.</p>']
    for cfg in obj['reminder_settings']:parts.append('<p>'+esc(cfg['mode'].upper())+' schedule: '+esc(', '.join(map(str,cfg['days'])))+' days overdue; repeat every '+esc(cfg['repeat_days'])+' days after the last stage (0 = off); '+esc(cfg['send_hour'])+':00 Bahamas time. Saved enabled: '+esc(cfg['enabled'])+'</p>')
    for cfg in obj['reminder_settings']:
        if 'messages' in cfg:
            parts.append('<p>Credit reminders before and on the due date: '+esc(cfg['credit_reminders'])+'. Eligibility uses the payment terms saved on the customer and the invoice’s agreed dates.</p>')
            for name,body in cfg['messages'].items():parts.append('<h2>'+esc(name)+'</h2><pre style="white-space:pre-wrap">'+esc(body)+'</pre>')
    parts.append('<table><tr><th>Mode / date</th><th>Invoice</th><th>Stage</th><th>Recipient / state</th><th>Retained PDF</th></tr>')
    for r in obj['reminder_deliveries']:parts.append('<tr><td>'+esc(r['mode'].upper()+' / '+r['sent_date'])+'</td><td>'+esc(r['invoice']['number'])+'</td><td>'+esc(stage_label(r['stage']))+'</td><td>'+esc(r['recipient']+' / '+r['state'])+'</td><td><a href="'+esc(r['id'])+'.pdf">Open reminder</a></td></tr>')
    return ''.join(parts)+'</table>'
