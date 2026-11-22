"""Validate retained send attempts, immutable contents and provider result history."""
import re
from email_delivery import address,clean,checked_pdf,canonical
from recover_crm import require,uid,date

FIELDS={'id','kind','document_id','document_version','document_number','recipient','sender','reply_to','subject','message','test_delivery','pdf_filename','pdf_sha256','pdf_base64','state','provider_id','error_code','actor_id','created_at','updated_at'}
MUTABLE={'state','provider_id','error_code','updated_at'}
def validate_emails(obj):
    rows=obj['email_deliveries'];events=obj['email_events']
    require(isinstance(rows,list) and len(rows)<=1000 and isinstance(events,list) and len(events)<=2000)
    docs={kind:{r['id']:r for r in obj[table]} for kind,table in [('quote','quotes'),('invoice','invoices'),('catalogue','client_catalogues')]}
    members={m['user_id'] for m in obj['staff_members']};records={};duplicates=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)==FIELDS);uid(row['id']);uid(row['document_id']);uid(row['actor_id']);require(row['actor_id'] in members)
        require(row['id'] not in records and row['kind'] in docs and row['document_id'] in docs[row['kind']])
        source=docs[row['kind']][row['document_id']]
        require(type(row['document_version']) is int and 1<=row['document_version']<=source['version'])
        require(row['document_number']==source.get('number',source.get('title')))
        if row['kind']!='catalogue':require(source['status']=='issued' and source['version']==row['document_version'])
        require(address(row['recipient'])==row['recipient'] and address(row['reply_to'])==row['reply_to'])
        require(clean(row['sender'],300,True)==row['sender'] and clean(row['subject'],160,True)==row['subject'] and clean(row['message'],4000)==row['message'])
        require(type(row['test_delivery']) is bool)
        if row['test_delivery']:require(row['subject'].startswith('TEST - ') and row['message'].startswith('TEST DELIVERY - '))
        if row['kind']=='invoice' and source['is_test']:require(row['test_delivery'])
        checked_pdf(row);require(date(row['updated_at'])>=date(row['created_at']))
        require(row['state'] in ('attempted','accepted','rejected','uncertain'))
        require((row['state']=='accepted')==(row['provider_id'] is not None))
        require((row['state'] in ('rejected','uncertain'))==(row['error_code'] is not None))
        if row['provider_id'] is not None:require(isinstance(row['provider_id'],str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',row['provider_id']) is not None)
        if row['error_code'] is not None:require(isinstance(row['error_code'],str) and re.fullmatch('[A-Z0-9_]{1,80}',row['error_code']) is not None)
        if row['state']!='rejected':
            key=tuple(row[k] for k in ('kind','document_id','pdf_sha256','recipient','test_delivery'));require(key not in duplicates);duplicates.add(key)
        records[row['id']]=row
    seen=set();latest={}
    for event in sorted(events,key=lambda x:x.get('id',0) if isinstance(x,dict) and type(x.get('id')) is int else 0):
        require(isinstance(event,dict) and set(event)=={'id','email_id','actor_id','happened_at','from_state','to_state','provider_id','error_code','record_snapshot'})
        require(type(event['id']) is int and event['id']>0 and event['id'] not in seen);seen.add(event['id']);uid(event['actor_id']);require(event['actor_id'] in members)
        require(event['email_id'] in records);r=event['record_snapshot'];before=latest.get(event['email_id'])
        require(isinstance(r,dict) and set(r)==FIELDS-{'pdf_base64'} and r['id']==event['email_id'])
        require(event['to_state']==r['state'] and event['provider_id']==r['provider_id'] and event['error_code']==r['error_code'])
        require(date(event['happened_at'])==date(r['updated_at']))
        if before is None:
            require(event['from_state'] is None and r['state']=='attempted' and r['provider_id'] is None and r['error_code'] is None and r['actor_id']==event['actor_id'] and r['created_at']==r['updated_at'])
        else:
            require(event['from_state']=='attempted' and before['state']=='attempted' and r['state'] in ('accepted','rejected','uncertain') and date(r['updated_at'])>=date(before['updated_at']))
            require({k:v for k,v in before.items() if k not in MUTABLE}=={k:v for k,v in r.items() if k not in MUTABLE})
        latest[r['id']]=r
    require(latest=={ident:{k:v for k,v in row.items() if k!='pdf_base64'} for ident,row in records.items()})
    return rows
