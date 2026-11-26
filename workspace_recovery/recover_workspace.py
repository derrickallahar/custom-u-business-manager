"""Offline-only combined CRM, quote and business-profile recovery verification."""
import base64,getpass,hashlib,json,sqlite3,sys,tempfile
from contextlib import closing
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'offline_recovery'))
from recover_crm import validate as validate_crm,restore as restore_crm,canonical,require,uid,date,check_record
from backup_codec import encrypt as encrypt_crm
from workspace_codec import decrypt,parse,MAX_BYTES
from quote_rules import normalize_profile,validate_saved_quote
from admin_control_rules import number_ok,validate_admin_controls
from invoice_rules import validate_invoice_document
from payment_rules import validate_payments
from adjustment_rules import validate_adjustments
from staff_rules import validate_staff
from job_rules import validate_jobs
from artwork_rules import validate_workspace_artwork
from product_rules import validate_products
from catalogue_rules import validate_catalogue
from mockup_rules import validate_mockups
from product_images import checked_bytes
from client_catalogue_rules import validate_client_catalogues,assets_for
from catalogue_pdf import render_catalogue
from opening_rules import validate_opening
from legacy_rules import validate_legacy
from reminder_rules import validate_reminders,history_html as reminder_history_html
from legacy_print import printable as legacy_printable
from opening_print import printable as opening_printable
from email_rules import validate_emails
from email_delivery import checked_pdf

def timestamps(r):
    require(type(r['version']) is int and 1<=r['version']<=1000000000)
    require(date(r['updated_at'])>=date(r['created_at']))

def profile_record(r):
    require(isinstance(r,dict) and set(r)=={'id','data','version','created_at','updated_at'} and r['id']=='business')
    timestamps(r);require(normalize_profile(r['data'])==r['data'])

def party(d,kind):
    # Reuse the CRM field validation without manufacturing a persisted record.
    r={'id':'10000000-0000-4000-8000-000000000001','kind':kind,'customer_id':None if kind=='customer' else '10000000-0000-4000-8000-000000000002',
       'data':d,'active':True,'version':1,'created_at':'2026-01-01T00:00:00+00:00','updated_at':'2026-01-01T00:00:00+00:00'}
    check_record(r)

def quote_record(r,crm):
    require(isinstance(r,dict) and set(r)=={'id','serial','number','status','version','customer_id','contact_id','customer_snapshot','contact_snapshot','seller_snapshot','data','created_at','updated_at'})
    uid(r['id']);timestamps(r);require(type(r['serial']) is int and 1<=r['serial']<=99999999 and number_ok(r['number'],r['serial'],'quote'))
    require(r['status'] in ('draft','issued'));uid(r['customer_id'])
    require(r['customer_id'] in crm and crm[r['customer_id']]['kind']=='customer');party(r['customer_snapshot'],'customer')
    if r['contact_id'] is not None:
        uid(r['contact_id']);require(r['contact_id'] in crm and crm[r['contact_id']]['kind']=='contact' and crm[r['contact_id']]['customer_id']==r['customer_id']);party(r['contact_snapshot'],'contact')
    else:require(r['contact_snapshot'] is None)
    require(normalize_profile(r['seller_snapshot'])==r['seller_snapshot']);validate_saved_quote(r['data'])
    if r['status']=='issued' and r['data']['tax_cents']>0:require(bool(r['seller_snapshot']['tax_id'].strip()))

def validate_097(obj):
    require(isinstance(obj,dict) and set(obj)=={'format','source_project','exported_at','crm','profile','quotes','audit'})
    require(obj['format']=='custom-u-workspace-snapshot-097' and obj['source_project']=='ldzugsrflgrlxmntbqtc');date(obj['exported_at']);validate_crm(obj['crm'])
    require(obj['crm']['exported_at']==obj['exported_at'])
    crm={r['id']:r for r in obj['crm']['records']};records={}
    if obj['profile'] is not None:profile_record(obj['profile']);records[('profile','business')]=obj['profile']
    require(isinstance(obj['quotes'],list) and len(obj['quotes'])<=5000 and isinstance(obj['audit'],list) and len(obj['audit'])<=100000)
    numbers=set()
    for r in obj['quotes']:
        quote_record(r,crm);key=('quote',r['id']);require(key not in records and r['number'] not in numbers);records[key]=r;numbers.add(r['number'])
    seen=set();latest={}
    for a in sorted(obj['audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','entity','entity_id','actor_id','happened_at','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id']);date(a['happened_at'])
        key=(a['entity'],a['entity_id']);require(key in records);before=a['before_record'];after=a['after_record'];require(before==latest.get(key));require(after['id']==a['entity_id'])
        if a['entity']=='profile':profile_record(after)
        else:quote_record(after,crm)
        if before is None:require(after['version']==1 and (a['entity']!='quote' or after['status']=='draft'))
        else:
            require(after['version']==before['version']+1 and after['created_at']==before['created_at'])
            if a['entity']=='quote':
                require(before['status'] in ('draft','issued') and after['number']==before['number'] and after['serial']==before['serial'] and after['seller_snapshot']==before['seller_snapshot'])
                if before['status']=='issued':
                    require(after['status']=='issued')
                    require({k:v for k,v in after.items() if k not in ('data','version','updated_at')}=={k:v for k,v in before.items() if k not in ('data','version','updated_at')})
                elif after['status']=='issued':
                    require({k:v for k,v in after.items() if k not in ('status','version','updated_at')}=={k:v for k,v in before.items() if k not in ('status','version','updated_at')})
        latest[key]=after
    require(latest==records)
    return obj

def base_snapshot(obj):
    return {**{k:v for k,v in obj.items() if k not in ('invoices','invoice_audit')},'format':'custom-u-workspace-snapshot-097'}

def validate_098(obj):
    if isinstance(obj,dict) and obj.get('format')=='custom-u-workspace-snapshot-097':return validate_097(obj)
    require(isinstance(obj,dict) and set(obj)=={'format','source_project','exported_at','crm','profile','quotes','audit','invoices','invoice_audit'} and obj['format']=='custom-u-workspace-snapshot-098')
    validate_097(base_snapshot(obj));quotes={(a['after_record']['id'],a['after_record']['version']):a['after_record'] for a in obj['audit'] if a['entity']=='quote'}
    require(isinstance(obj['invoices'],list) and len(obj['invoices'])<=5000 and isinstance(obj['invoice_audit'],list) and len(obj['invoice_audit'])<=100000)
    crm_versions={(a['after_record']['id'],a['after_record']['version']):a['after_record'] for a in obj['crm']['audit']}
    seller_versions={a['after_record']['version']:a['after_record'] for a in obj['audit'] if a['entity']=='profile'}
    def invoice(r):
        require(isinstance(r,dict) and set(r)=={'id','serial','number','is_test','quote_id','quote_version','quote_snapshot','details','status','version','created_at','updated_at'})
        uid(r['id']);timestamps(r);require(type(r['serial']) is int and 1<=r['serial']<=99999999)
        require(number_ok(r['number'],r['serial'],'invoice',r['is_test']));validate_invoice_document(r)
        if r['quote_id'] is not None:
            q=dict(r['quote_snapshot'])
            if 'original_quote_data' in q:q['data']=q.pop('original_quote_data')
            require(q==quotes.get((r['quote_id'],r['quote_version'])))
        else:
            q=r['quote_snapshot'];c=crm_versions.get((q['customer_id'],q['customer_version']));require(c is not None and c['kind']=='customer' and c['data']==q['customer_snapshot']);party(q['customer_snapshot'],'customer')
            if q['contact_id'] is not None:
                c=crm_versions.get((q['contact_id'],q['contact_version']));require(c is not None and c['kind']=='contact' and c['customer_id']==q['customer_id'] and c['data']==q['contact_snapshot']);party(q['contact_snapshot'],'contact')
            seller=seller_versions.get(q['seller_version']);require(seller is not None and seller['data']==q['seller_snapshot'])
    records={};numbers=set();sources=set()
    for r in obj['invoices']:
        invoice(r);require(r['id'] not in records and r['number'] not in numbers and (r['quote_id'] is None or (r['quote_id'],r['is_test']) not in sources))
        records[r['id']]=r;numbers.add(r['number']);sources.add((r['quote_id'],r['is_test']))
    seen=set();latest={}
    for a in sorted(obj['invoice_audit'],key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','invoice_id','actor_id','happened_at','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id']);date(a['happened_at'])
        require(a['invoice_id'] in records);before=a['before_record'];after=a['after_record'];require(before==latest.get(a['invoice_id']));invoice(after);require(after['id']==a['invoice_id'])
        if before is None:require(after['version']==1 and after['status']=='draft')
        else:
            require(before['status'] in ('draft','issued') and after['version']==before['version']+1)
            mutable=('details','status','version','updated_at')+ (('quote_snapshot',) if after['quote_id'] is None else ()) if after['status']=='draft' else ('status','version','updated_at')
            if before['status']=='issued':
                require(after['status']=='issued')
                mutable=('details','quote_snapshot','version','updated_at')
                bq=dict(before['quote_snapshot']);aq=dict(after['quote_snapshot'])
                bq.pop('data');aq.pop('data')
                if before['quote_id'] is not None:
                    require(aq.pop('original_quote_data',None)==bq.pop('original_quote_data',before['quote_snapshot']['data']))
                require(aq==bq)
            if after['quote_id'] is None:require(before['quote_snapshot']['seller_snapshot']==after['quote_snapshot']['seller_snapshot'] and before['quote_snapshot']['seller_version']==after['quote_snapshot']['seller_version'])
            require({k:v for k,v in before.items() if k not in mutable}=={k:v for k,v in after.items() if k not in mutable})
        latest[a['invoice_id']]=after
    require(latest==records);return obj

def validate_099(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-099':return validate_098(obj)
    require(set(obj)=={'format','source_project','exported_at','crm','profile','quotes','audit','invoices','invoice_audit','payments','payment_audit'})
    validate_098({**{k:v for k,v in obj.items() if k not in ('payments','payment_audit')},'format':'custom-u-workspace-snapshot-098'})
    validate_payments(obj);return obj

def validate_100(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-100':return validate_099(obj)
    require(set(obj)=={'format','source_project','exported_at','crm','profile','quotes','audit','invoices','invoice_audit','payments','payment_audit','credits','refunds','adjustment_audit'})
    validate_099({**{k:v for k,v in obj.items() if k not in ('credits','refunds','adjustment_audit')},'format':'custom-u-workspace-snapshot-099'})
    validate_adjustments(obj);return obj

def validate_102(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-102':return validate_100(obj)
    fields=('staff_access','staff_audit','staff_members','staff_enabled')
    require(all(k in obj for k in fields))
    validate_100({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-100'})
    validate_staff(obj);return obj

def validate_103(obj,allow_artwork=False):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-103':return validate_102(obj)
    require(all(k in obj for k in ('jobs','job_audit')))
    validate_102({**{k:v for k,v in obj.items() if k not in ('jobs','job_audit')},'format':'custom-u-workspace-snapshot-102'})
    validate_jobs(obj,allow_artwork=allow_artwork);return obj

def validate_104(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-104':return validate_103(obj)
    fields=('artwork_files','artwork_heads','artwork_audit');require(all(k in obj for k in fields))
    validate_103({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-103'},allow_artwork=True)
    validate_workspace_artwork(obj);return obj

def validate_105(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-105':return validate_104(obj)
    fields=('products','product_audit');require(all(k in obj for k in fields))
    validate_104({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-104'})
    validate_products(obj);return obj

def validate_106(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-106':return validate_105(obj)
    fields=('product_sources','product_source_audit','product_images','product_image_audit');require(all(k in obj for k in fields))
    validate_105({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-105'})
    validate_catalogue(obj);return obj

def validate_107(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-107':return validate_106(obj)
    fields=('mockups','mockup_audit');require(all(k in obj for k in fields))
    validate_106({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-106'})
    validate_mockups(obj);return obj

def validate_108(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-108':return validate_107(obj)
    fields=('client_catalogues','client_catalogue_audit');require(all(k in obj for k in fields))
    validate_107({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-107'})
    validate_client_catalogues(obj);return obj

def validate_109(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-109':return validate_108(obj)
    fields=('email_deliveries','email_events');require(all(k in obj for k in fields))
    validate_108({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-108'})
    validate_emails(obj);return obj

def validate_110(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-110':return validate_109(obj)
    fields=('opening_batches','opening_audit');require(all(k in obj for k in fields))
    validate_109({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-109'})
    validate_opening(obj);return obj

def validate_111(obj):
    if not isinstance(obj,dict) or obj.get('format')!='custom-u-workspace-snapshot-111':return validate_110(obj)
    fields={'legacy_books','legacy_entries','legacy_events','legacy_audit'}
    require(fields<=set(obj))
    validate_110({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-110'})
    validate_legacy(obj);return obj

def validate(obj):
    if isinstance(obj,dict) and obj.get('format')=='custom-u-workspace-snapshot-118':
        validate_admin_controls(obj)
        validate({**{k:v for k,v in obj.items() if k!='admin_controls'},'format':'custom-u-workspace-snapshot-114'})
        return obj
    if not isinstance(obj,dict) or obj.get('format') not in ('custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114'):return validate_111(obj)
    fields={'reminder_settings','reminder_deliveries','reminder_audit'}
    require(fields<=set(obj))
    validate_111({**{k:v for k,v in obj.items() if k not in fields},'format':'custom-u-workspace-snapshot-111'})
    validate_reminders(obj);return obj

def restore(blob,password,parent,*,progress=None):
    step=progress if progress is not None else lambda stage:None
    step('DECRYPT')
    raw=decrypt(blob,password)
    step('SNAPSHOT_PARSE')
    snapshot=parse(raw)
    step('VALIDATION')
    snapshot=validate(snapshot)
    has_invoices=snapshot['format'] in ('custom-u-workspace-snapshot-098','custom-u-workspace-snapshot-099','custom-u-workspace-snapshot-100','custom-u-workspace-snapshot-102','custom-u-workspace-snapshot-103','custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_payments=snapshot['format'] in ('custom-u-workspace-snapshot-099','custom-u-workspace-snapshot-100','custom-u-workspace-snapshot-102','custom-u-workspace-snapshot-103','custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_adjustments=snapshot['format'] in ('custom-u-workspace-snapshot-100','custom-u-workspace-snapshot-102','custom-u-workspace-snapshot-103','custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_staff=snapshot['format'] in ('custom-u-workspace-snapshot-102','custom-u-workspace-snapshot-103','custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_jobs=snapshot['format'] in ('custom-u-workspace-snapshot-103','custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_artwork=snapshot['format'] in ('custom-u-workspace-snapshot-104','custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_products=snapshot['format'] in ('custom-u-workspace-snapshot-105','custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_catalogue=snapshot['format'] in ('custom-u-workspace-snapshot-106','custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_mockups=snapshot['format'] in ('custom-u-workspace-snapshot-107','custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_client_catalogues=snapshot['format'] in ('custom-u-workspace-snapshot-108','custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_emails=snapshot['format'] in ('custom-u-workspace-snapshot-109','custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_opening=snapshot['format'] in ('custom-u-workspace-snapshot-110','custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_legacy=snapshot['format'] in ('custom-u-workspace-snapshot-111','custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118');has_reminders=snapshot['format'] in ('custom-u-workspace-snapshot-112','custom-u-workspace-snapshot-113','custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118')
    step('LOCAL_RESTORE')
    # The existing 094 restoration verifies CRM and creates a fresh folder.
    folder,crm_report=restore_crm(encrypt_crm(canonical(snapshot['crm']).encode(),password),password,parent)
    database=folder/'recovered_crm.sqlite'
    with closing(sqlite3.connect(database)) as db:
        db.execute('CREATE TABLE admin_controls_backup(id INTEGER PRIMARY KEY CHECK(id=1),record_json TEXT NOT NULL)')
        db.executescript('CREATE TABLE reminder_settings(mode TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE reminder_deliveries(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE reminder_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE legacy_books(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE legacy_entries(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE legacy_events(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE legacy_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE opening_batches(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE opening_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE email_deliveries(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE email_events(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE client_catalogues(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE client_catalogue_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE mockups(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE mockup_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE product_sources(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE product_source_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE product_images(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE product_image_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        db.executescript('CREATE TABLE products(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE product_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE quote_profile(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE quotes(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE quote_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE workspace_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE invoices(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE invoice_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE payments(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE payment_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE credits(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE refunds(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE adjustment_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE staff_access(user_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE staff_members(user_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE staff_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE jobs(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE job_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE artwork_files(id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE artwork_heads(job_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);CREATE TABLE artwork_audit(id INTEGER PRIMARY KEY,record_json TEXT NOT NULL);')
        with db:
            if 'admin_controls' in snapshot:db.execute('INSERT INTO admin_controls_backup VALUES (1,?)',(canonical(snapshot['admin_controls']),))
            if snapshot['profile'] is not None:db.execute('INSERT INTO quote_profile VALUES (?,?)',('business',canonical(snapshot['profile'])))
            for q in snapshot['quotes']:db.execute('INSERT INTO quotes VALUES (?,?)',(q['id'],canonical(q)))
            for a in snapshot['audit']:db.execute('INSERT INTO quote_audit VALUES (?,?)',(a['id'],canonical(a)))
            for i in snapshot.get('invoices',[]):db.execute('INSERT INTO invoices VALUES (?,?)',(i['id'],canonical(i)))
            for a in snapshot.get('invoice_audit',[]):db.execute('INSERT INTO invoice_audit VALUES (?,?)',(a['id'],canonical(a)))
            for p in snapshot.get('payments',[]):db.execute('INSERT INTO payments VALUES (?,?)',(p['id'],canonical(p)))
            for a in snapshot.get('payment_audit',[]):db.execute('INSERT INTO payment_audit VALUES (?,?)',(a['id'],canonical(a)))
            for table in ('credits','refunds','adjustment_audit'):
                for r in snapshot.get(table,[]):db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_reminders:
                for table in ('reminder_settings','reminder_deliveries','reminder_audit'):
                    for row in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(row['mode'] if table=='reminder_settings' else row['id'],canonical(row)))
            if has_legacy:
                for table in ('legacy_books','legacy_entries','legacy_events','legacy_audit'):
                    for row in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(row['id'],canonical(row)))
            if has_opening:
                for table in ('opening_batches','opening_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_emails:
                for table in ('email_deliveries','email_events'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_client_catalogues:
                for table in ('client_catalogues','client_catalogue_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_mockups:
                for table in ('mockups','mockup_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_catalogue:
                for table in ('product_sources','product_source_audit','product_images','product_image_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_products:
                for table in ('products','product_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_artwork:
                for table in ('artwork_files','artwork_heads','artwork_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['job_id'] if table=='artwork_heads' else r['id'],canonical(r)))
            if has_jobs:
                for table in ('jobs','job_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'],canonical(r)))
            if has_staff:
                for table in ('staff_access','staff_members','staff_audit'):
                    for r in snapshot[table]:db.execute('INSERT INTO '+table+' VALUES (?,?)',(r['id'] if table=='staff_audit' else r['user_id'],canonical(r)))
                db.execute('INSERT INTO workspace_metadata VALUES (?,?)',('staff_enabled',canonical(snapshot['staff_enabled'])))
            for k in ('format','source_project','exported_at'):db.execute('INSERT INTO workspace_metadata VALUES (?,?)',(k,canonical(snapshot[k])))
    step('FIELD_COMPARISON')
    with closing(sqlite3.connect(database)) as db:
        require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok');require(not db.execute('PRAGMA foreign_key_check').fetchall())
        loaded={k:json.loads(v) for k,v in db.execute('SELECT key,value FROM workspace_metadata')};loaded['crm']=snapshot['crm']
        if 'admin_controls' in snapshot:
            loaded['admin_controls']=json.loads(db.execute('SELECT record_json FROM admin_controls_backup WHERE id=1').fetchone()[0])
            require(loaded['admin_controls']==snapshot['admin_controls']);validate_admin_controls(loaded)
        p=db.execute('SELECT record_json FROM quote_profile').fetchall();require(len(p)<=1);loaded['profile']=json.loads(p[0][0]) if p else None
        loaded['quotes']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM quotes ORDER BY id')]
        loaded['audit']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM quote_audit ORDER BY id')]
        if has_invoices:
            loaded['invoices']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM invoices ORDER BY id')]
            loaded['invoice_audit']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM invoice_audit ORDER BY id')]
        if has_payments:
            loaded['payments']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM payments ORDER BY id')]
            loaded['payment_audit']=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM payment_audit ORDER BY id')]
        if has_adjustments:
            for table in ('credits','refunds','adjustment_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table+' ORDER BY id')]
        if has_reminders:
            for table in ('reminder_settings','reminder_deliveries','reminder_audit'):loaded[table]=[json.loads(x[0]) for x in db.execute('SELECT record_json FROM '+table)]
        if has_legacy:
            for table in ('legacy_books','legacy_entries','legacy_events','legacy_audit'):loaded[table]=[json.loads(x[0]) for x in db.execute('SELECT record_json FROM '+table)]
        if has_opening:
            for table in ('opening_batches','opening_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_emails:
            for table in ('email_deliveries','email_events'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_client_catalogues:
            for table in ('client_catalogues','client_catalogue_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_mockups:
            for table in ('mockups','mockup_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_catalogue:
            for table in ('product_sources','product_source_audit','product_images','product_image_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_products:
            for table in ('products','product_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_artwork:
            for table in ('artwork_files','artwork_heads','artwork_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_jobs:
            for table in ('jobs','job_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
        if has_staff:
            for table in ('staff_access','staff_members','staff_audit'):loaded[table]=[json.loads(r[0]) for r in db.execute('SELECT record_json FROM '+table)]
    if has_reminders:
        for obj in (snapshot,loaded):
            for table in ('reminder_settings','reminder_deliveries','reminder_audit'):obj[table].sort(key=lambda x:x['mode'] if table=='reminder_settings' else x['id'])
    if has_legacy:
        for obj in (snapshot,loaded):
            for table in ('legacy_books','legacy_entries','legacy_events','legacy_audit'):obj[table].sort(key=lambda x:x['id'])
    if has_opening:
        for obj in (snapshot,loaded):
            for table in ('opening_batches','opening_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_emails:
        for obj in (snapshot,loaded):
            for table in ('email_deliveries','email_events'):obj[table].sort(key=lambda r:r['id'])
    if has_client_catalogues:
        for obj in (snapshot,loaded):
            for table in ('client_catalogues','client_catalogue_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_mockups:
        for obj in (snapshot,loaded):
            for table in ('mockups','mockup_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_catalogue:
        for obj in (snapshot,loaded):
            for table in ('product_sources','product_source_audit','product_images','product_image_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_products:
        for obj in (snapshot,loaded):
            for table in ('products','product_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_artwork:
        for obj in (snapshot,loaded):
            for table in ('artwork_files','artwork_heads','artwork_audit'):obj[table].sort(key=lambda r:r['job_id'] if table=='artwork_heads' else r['id'])
    if has_jobs:
        for obj in (snapshot,loaded):
            for table in ('jobs','job_audit'):obj[table].sort(key=lambda r:r['id'])
    if has_staff:
        for obj in (snapshot,loaded):
            for table in ('staff_access','staff_members','staff_audit'):obj[table].sort(key=lambda r:r['id'] if table=='staff_audit' else r['user_id'])
    for obj in (snapshot,loaded):obj['quotes'].sort(key=lambda r:r['id']);obj['audit'].sort(key=lambda r:r['id'])
    if has_invoices:
        for obj in (snapshot,loaded):obj['invoices'].sort(key=lambda r:r['id']);obj['invoice_audit'].sort(key=lambda r:r['id'])
    if has_payments:
        for obj in (snapshot,loaded):obj['payments'].sort(key=lambda r:r['id']);obj['payment_audit'].sort(key=lambda r:r['id'])
    if has_adjustments:
        for obj in (snapshot,loaded):
            for table in ('credits','refunds','adjustment_audit'):obj[table].sort(key=lambda r:r['id'])
    require(canonical(snapshot)==canonical(loaded));validate(loaded)
    step('RECOVERED_FILES')
    if has_catalogue:
        image_folder=folder/'catalogue_images';image_folder.mkdir()
        for image in snapshot['product_images']:
            raw=checked_bytes(image);target=image_folder/(image['id']+'.webp');target.write_bytes(raw);require(target.read_bytes()==raw)
    if has_mockups:
        target_folder=folder/'client_mockups';target_folder.mkdir()
        for r in snapshot['mockups']:
            for kind in ('logo','preview'):
                raw=checked_bytes(r[kind]);target=target_folder/(r['id']+'_'+kind+'.webp');target.write_bytes(raw);require(target.read_bytes()==raw)
    if has_client_catalogues:
        target_folder=folder/'client_catalogues';target_folder.mkdir()
        for r in snapshot['client_catalogues']:
            raw=render_catalogue(r,assets_for(r,snapshot));target=target_folder/(r['id']+'.pdf');target.write_bytes(raw);require(target.read_bytes()==raw)
    if has_emails:
        target_folder=folder/'email_attachments';target_folder.mkdir()
        for row in snapshot['email_deliveries']:
            raw=checked_pdf(row);target=target_folder/(row['id']+'.pdf');target.write_bytes(raw);require(target.read_bytes()==raw)
    if has_opening:
        target=folder/'opening_rehearsals';target.mkdir()
        for row in snapshot['opening_batches']:
            raw=base64.b64decode(row['csv_base64'],validate=True)
            (target/(row['id']+'.csv')).write_bytes(raw)
            require((target/(row['id']+'.csv')).read_bytes()==raw)
            (target/(row['id']+'.html')).write_text(opening_printable(row),encoding='utf-8')
            (target/(row['id']+'.json')).write_text(canonical({k:v for k,v in row.items() if k!='csv_base64'}),encoding='utf-8')
    if has_legacy:
        target=folder/'legacy_balances';target.mkdir()
        for book in snapshot['legacy_books']:
            entries=[e for e in snapshot['legacy_entries'] if e['book_id']==book['id']];ids={e['id'] for e in entries}
            state={'mode':book['mode'],'book':book,'source':next(x for x in snapshot['opening_batches'] if x['id']==book['source_id']),'entries':entries,'events':[e for e in snapshot['legacy_events'] if e['entry_id'] in ids]}
            (target/(book['mode']+'_balance_register.html')).write_text(legacy_printable(state),encoding='utf-8')
    if has_reminders:
        target=folder/'reminders';target.mkdir()
        for row in snapshot['reminder_deliveries']:
            raw=checked_pdf(row);destination=target/(row['id']+'.pdf');destination.write_bytes(raw);require(destination.read_bytes()==raw)
        (target/'reminder_history.html').write_text(reminder_history_html(snapshot),encoding='utf-8')
    report={'reminders_verified':has_reminders,'reminder_deliveries':len(snapshot.get('reminder_deliveries',[])),'reminder_audit_entries':len(snapshot.get('reminder_audit',[])),'legacy_books':len(snapshot.get('legacy_books',[])),'legacy_entries':len(snapshot.get('legacy_entries',[])),'legacy_events':len(snapshot.get('legacy_events',[])),'legacy_audit_entries':len(snapshot.get('legacy_audit',[])),'legacy_verified':has_legacy,'opening_rehearsals':len(snapshot.get('opening_batches',[])),'opening_audit_entries':len(snapshot.get('opening_audit',[])),'opening_source_bytes_verified':has_opening,'emails':len(snapshot.get('email_deliveries',[])),'email_events':len(snapshot.get('email_events',[])),'email_bytes_included':has_emails,'client_catalogues':len(snapshot.get('client_catalogues',[])),'client_catalogue_audit_entries':len(snapshot.get('client_catalogue_audit',[])),'client_catalogues_rebuilt':has_client_catalogues,'mockups':len(snapshot.get('mockups',[])),'mockup_audit_entries':len(snapshot.get('mockup_audit',[])),'mockup_bytes_included':has_mockups,'product_sources':len(snapshot.get('product_sources',[])),'supplier_audit_entries':len(snapshot.get('product_source_audit',[])),'catalogue_images':len(snapshot.get('product_images',[])),'image_audit_entries':len(snapshot.get('product_image_audit',[])),'catalogue_image_bytes_included':has_catalogue,'products':len(snapshot.get('products',[])),'product_audit_entries':len(snapshot.get('product_audit',[])),'result':'PASS','customers':crm_report['customers'],'contacts':crm_report['contacts'],'crm_audit_entries':crm_report['audit_entries'],
            'quotes':len(snapshot['quotes']),'business_profiles':int(snapshot['profile'] is not None),'quote_audit_entries':len(snapshot['audit']),
            'direct_invoices':sum(i['quote_id'] is None for i in snapshot.get('invoices',[])),'invoices':len(snapshot.get('invoices',[])),'test_invoices':sum(i['is_test'] for i in snapshot.get('invoices',[])),'invoice_audit_entries':len(snapshot.get('invoice_audit',[])),'snapshot_format':snapshot['format'],
            'payments':len(snapshot.get('payments',[])),'recorded_payments':sum(p['status']=='recorded' for p in snapshot.get('payments',[])),'reversed_payments':sum(p['status']=='reversed' for p in snapshot.get('payments',[])),'test_payments':sum(p['is_test'] for p in snapshot.get('payments',[])),'payment_audit_entries':len(snapshot.get('payment_audit',[])),
            'credits':len(snapshot.get('credits',[])),'issued_credits':sum(c['status']=='issued' for c in snapshot.get('credits',[])),'refunds':len(snapshot.get('refunds',[])),'recorded_refunds':sum(r['status']=='recorded' for r in snapshot.get('refunds',[])),'reversed_refunds':sum(r['status']=='reversed' for r in snapshot.get('refunds',[])),'adjustment_audit_entries':len(snapshot.get('adjustment_audit',[])),
            'artwork_files':len(snapshot.get('artwork_files',[])),'artwork_file_bytes_included':False,'jobs':len(snapshot.get('jobs',[])),'test_jobs':sum(j['is_test'] for j in snapshot.get('jobs',[])),'job_audit_entries':len(snapshot.get('job_audit',[])),'staff_members':len(snapshot.get('staff_members',[])),'staff_access_settings':len(snapshot.get('staff_access',[])),'staff_audit_entries':len(snapshot.get('staff_audit',[])),'all_fields_compared':True,'backup_sha256':hashlib.sha256(blob).hexdigest(),'scope':'Local SQLite restoration; not a hosted PostgreSQL restore','unencrypted_local_database':True}
    if 'admin_controls' in snapshot:
        report['administrator_controls_verified']=True;report['administrator_control_records']=len(snapshot['admin_controls']['records']);report['administrator_control_audit_entries']=len(snapshot['admin_controls']['audit'])
        target=folder/'administrator_controls.json';target.write_text(canonical(snapshot['admin_controls']),encoding='utf-8');require(json.loads(target.read_text(encoding='utf-8'))==snapshot['admin_controls'])
    step('REPORT_WRITE')
    (folder/'workspace_recovery_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return folder,report

def failure_details(exc,stage):
    # Use fixed messages only; exceptions may include private paths or record data.
    if isinstance(exc,ZoneInfoNotFoundError):
        return ('TIMEZONE_DATA_MISSING','Run SETUP_WINDOWS.bat from this updated folder, then retry. Your passphrase has not been rejected.')
    if isinstance(exc,FileNotFoundError) and stage=='FILE_READ':
        return ('BACKUP_FILE_NOT_FOUND','The backup path could not be found. Use the full path to the downloaded .cuwork file.')
    if isinstance(exc,PermissionError):
        return ('LOCAL_ACCESS_DENIED','Check access to the backup and the extracted recovery folder, then retry.')
    if isinstance(exc,OSError):
        return ('LOCAL_FILE_ERROR','Check file access and free disk space. This is not a passphrase check failure.')
    if isinstance(exc,ValueError) and exc.args and exc.args[0] in ('WRONG_PASSPHRASE_OR_DAMAGED_BACKUP','INVALID_BACKUP_FILE','BACKUP_SIZE'):
        code=exc.args[0]
        messages={
            'WRONG_PASSPHRASE_OR_DAMAGED_BACKUP':'The encrypted file could not be authenticated. Check its passphrase or try a fresh backup.',
            'INVALID_BACKUP_FILE':'This file is not a supported encrypted workspace backup.',
            'BACKUP_SIZE':'The backup exceeds the supported size limit.'}
        return code,messages[code]
    if stage=='VALIDATION':
        return ('SNAPSHOT_VALIDATION_FAILED','Decryption succeeded, but record or audit validation did not complete. Share this code and stage for investigation.')
    return ('RECOVERY_CHECK_FAILED','Share this code and stage for investigation. Do not share your passphrase.')

def main():
    print('CUSTOM U — LOCAL WORKSPACE RECOVERY CHECK 118')
    print('No cloud connections. Creates a NEW local recovery folder; existing databases are not replaced.')
    print('The recovered database is UNENCRYPTED. Your .cuwork backup remains encrypted.')
    stage='SETUP';password=None
    def progress(value):
        nonlocal stage
        stage=value
        print('Checking:',value)
    try:
        ZoneInfo('America/Nassau')
        path=input('Full path to your downloaded .cuwork backup: ').strip().strip('"')
        stage='FILE_READ';p=Path(path)
        if p.stat().st_size>MAX_BYTES+100:raise ValueError('BACKUP_SIZE')
        blob=p.read_bytes()
        stage='PASSPHRASE';password=getpass.getpass('Backup passphrase (hidden): ')
        folder,report=restore(blob,password,Path(__file__).resolve().parent,progress=progress)
        print('DECRYPT / AUDIT CHAINS / LOCAL RESTORE / ALL-FIELD COMPARISON: PASS')
        print('Customers:',report['customers'],'Contacts:',report['contacts'],'Quotes:',report['quotes'])
        print('CRM audit entries:',report['crm_audit_entries'],'Quote/profile audit entries:',report['quote_audit_entries'])
        print('Invoices:',report['invoices'],'(test:',report['test_invoices'],') Invoice audit entries:',report['invoice_audit_entries'])
        if report['snapshot_format'] in ('custom-u-workspace-snapshot-114','custom-u-workspace-snapshot-118'):print('Direct invoices:',report['direct_invoices'],'DIRECT INVOICES / SAVED ITEMS / AUDIT REPLAY: PASS')
        print('Payments:',report['payments'],'(recorded:',report['recorded_payments'],'reversed:',report['reversed_payments'],'test:',report['test_payments'],') Payment audit entries:',report['payment_audit_entries'])
        print('Credit notes:',report['credits'],'(issued:',report['issued_credits'],') Refunds:',report['refunds'],'(recorded:',report['recorded_refunds'],'reversed:',report['reversed_refunds'],') Adjustment audit entries:',report['adjustment_audit_entries'])
        print('Staff members:',report['staff_members'],'Access settings:',report['staff_access_settings'],'Staff audit entries:',report['staff_audit_entries'])
        print('Staff settings are a local record only. Cloud accounts and sessions are not restored.')
        print('Jobs:',report['jobs'],'(test:',report['test_jobs'],') Job audit entries:',report['job_audit_entries'])
        print('Products:',report['products'],'Product audit entries:',report['product_audit_entries'])
        print('Supplier records:',report['product_sources'],'Supplier audit entries:',report['supplier_audit_entries'])
        print('Catalogue images:',report['catalogue_images'],'Image audit entries:',report['image_audit_entries'])
        if report['catalogue_image_bytes_included']:print('CATALOGUE IMAGE CHECKSUMS / DECODE / BYTE COMPARISON: PASS')
        if report['mockup_bytes_included']:
            print('Client mockups:',report['mockups'],'Mockup audit entries:',report['mockup_audit_entries'])
            print('MOCKUP LOGO + PREVIEW CHECKSUMS / DECODE / BYTE COMPARISON: PASS')
        if report['client_catalogues_rebuilt']:
            print('Client catalogues:',report['client_catalogues'],'Catalogue audit entries:',report['client_catalogue_audit_entries'])
            print('CLIENT CATALOGUE RECORDS / IMAGE REFERENCES / PDF REBUILD: PASS')
        if report['email_bytes_included']:
            print('Email requests:',report['emails'],'Email events:',report['email_events'])
            print('EMAIL HISTORY / PDF CHECKSUMS / BYTE COMPARISON: PASS')
        if report['opening_source_bytes_verified']:
            print('Opening-balance rehearsals:',report['opening_rehearsals'],'Opening audit entries:',report['opening_audit_entries'])
            print('OPENING BALANCES / CUSTOMER MATCHES / CSV CHECKSUMS / BYTE COMPARISON: PASS')
        if report['legacy_verified']:
            print('Legacy ledgers:',report['legacy_books'],'Imported balances:',report['legacy_entries'],'Later activity:',report['legacy_events'],'Legacy audit entries:',report['legacy_audit_entries'])
            print('LEGACY BALANCES / PAYMENTS / CREDITS / REVERSALS / AUDIT REPLAY: PASS')
        if report['reminders_verified']:
            print('Reminder deliveries:',report['reminder_deliveries'],'Reminder audit entries:',report['reminder_audit_entries'])
            print('REMINDER SCHEDULES / HISTORY / AUDIT / PDF BYTE COMPARISON: PASS')
        print('Artwork metadata records:',report['artwork_files'])
        print('Artwork FILE BYTES are separate. Check each job .cuart with CHECK_ARTWORK_BACKUP_WINDOWS.bat.')
        print('Recovery folder:',folder)
        if report.get('administrator_controls_verified'):print('ADMIN CONTROLS / NETWORK ACCESS / NUMBERING / DISCOUNTS / AUDIT REPLAY: PASS')
        print('Keep the encrypted backup and passphrase separately. Remove the recovery folder when no longer needed.')
    except (KeyboardInterrupt,EOFError):
        print('CHECK CANCELLED. No production data was changed.');return 1
    except Exception as exc:
        code,message=failure_details(exc,stage)
        print('CHECK FAILED. Code:',code,'Stage:',stage)
        print(message)
        print('No production data was changed.');return 1
    finally:password=None
    return 0

if __name__=='__main__':sys.exit(main())
