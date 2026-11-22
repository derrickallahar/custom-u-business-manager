"""Offline validation of team records, original file bytes and immutable messages."""
import base64,hashlib,re
from datetime import date,datetime
FIELDS={'full_name','birth_date','nib_number','drivers_license_number','passport_number','phone','personal_email','address','emergency_name','emergency_relationship','emergency_phone','job_title','department','start_date','end_date','notes'}
IDENTIFIERS={'nib_number','drivers_license_number','passport_number'}
TEAM_KEYS={'team_records','team_files','team_audit','team_messages','team_reads','team_acks','team_requests'}
def need(v):
    if not v:raise ValueError('INVALID_TEAM_DATA')
def uid(v):need(isinstance(v,str) and re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',v))
def stamp(v):
    need(isinstance(v,str));d=datetime.fromisoformat(v.replace('Z','+00:00'));need(d.tzinfo is not None);return d
def text(v,n):need(isinstance(v,str) and len(v)<=n and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',v))
def check_record(r):
    need(set(r)=={'id','kind','employee_id','data','version','created_at','updated_at'});uid(r['id']);need(type(r['version']) is int and r['version']>0);need(stamp(r['updated_at'])>=stamp(r['created_at']));d=r['data'];need(isinstance(d,dict))
    if r['employee_id'] is not None:uid(r['employee_id'])
    if r['kind']=='profile':
        need(r['employee_id'] and set(d)==FIELDS)
        for k,v in d.items():
            text(v,2000 if k in ('address','notes') else 60 if k in IDENTIFIERS else 254)
            if k in ('birth_date','start_date','end_date') and v:date.fromisoformat(v)
        if d['end_date']:need(d['start_date'] and d['end_date']>=d['start_date'])
    elif r['kind']=='intake':
        need(r['employee_id'] and set(d)==IDENTIFIERS and r['version']==1)
        for v in d.values():text(v,60)
        need(any(d.values()))
    elif r['kind']=='document':
        need(r['employee_id'] and set(d)=={'filename','mime','size_bytes','sha256','category','expiry_date','active','uploaded_by'})
        text(d['filename'],180);need(d['filename'] and not re.search(r'[<>:"|?*\x00-\x1f\x7f/\\]',d['filename']));need(d['mime'] in ('application/pdf','image/png','image/jpeg'))
        need(type(d['size_bytes']) is int and 0<d['size_bytes']<=5242880);need(re.fullmatch('[a-f0-9]{64}',d['sha256']));need(type(d['active']) is bool);uid(d['uploaded_by'])
        need(d['category'] in ('Police record','Reference','Driver licence','Passport','Employment contract','Other'))
        if d['expiry_date']:date.fromisoformat(d['expiry_date'])
    elif r['kind']=='bulletin':
        need(r['employee_id'] is None and set(d)=={'title','body','state','pinned','require_ack','author_id','updated_by'})
        text(d['title'],160);text(d['body'],12000);need(d['title'] and d['body'] and d['state'] in ('draft','published','archived'));need(type(d['pinned']) is bool and type(d['require_ack']) is bool);uid(d['author_id']);uid(d['updated_by'])
    else:raise ValueError('INVALID_TEAM_DATA')
def checked_file(record,encoded):
    check_record(record);need(record['kind']=='document' and isinstance(encoded,str) and len(encoded)<=6990508)
    raw=base64.b64decode(encoded,validate=True);d=record['data'];need(len(raw)==d['size_bytes'] and hashlib.sha256(raw).hexdigest()==d['sha256'])
    magic={'application/pdf':b'%PDF-','image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff'};need(raw.startswith(magic[d['mime']]));return raw

def validate_team(obj):
    present=TEAM_KEYS&set(obj)
    if not present:return
    need(present==TEAM_KEYS)
    for k in TEAM_KEYS:need(isinstance(obj[k],list) and len(obj[k])<=150000)
    actual={};unique=set();people={p['id'] for p in obj['hr_people']}
    for r in obj['team_records']:
        check_record(r);need(r['id'] not in actual and (r['employee_id'] is None or r['employee_id'] in people));actual[r['id']]=r
        if r['kind'] in ('profile','intake'):
            key=(r['kind'],r['employee_id']);need(key not in unique);unique.add(key)
    latest={};versions={};seen=set()
    for a in sorted(obj['team_audit'],key=lambda a:a['id']):
        need(set(a)=={'id','record_id','actor_id','happened_at','before_record','after_record'} and type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id'])
        b=a['before_record'];r=a['after_record'];check_record(r);need(r['id']==a['record_id'] and latest.get(r['id'])==b);need(r['version']==(b['version']+1 if b else 1));need(r['updated_at']==a['happened_at'])
        if b:
            need(all(r[k]==b[k] for k in ('id','kind','employee_id','created_at')))
            if r['kind']=='document':need({k:v for k,v in r['data'].items() if k!='active'}=={k:v for k,v in b['data'].items() if k!='active'})
        latest[r['id']]=r;versions[(r['id'],r['version'])]=r
    need(actual==latest)
    files=set()
    for f in obj['team_files']:
        need(set(f)=={'id','content_base64'} and f['id'] not in files and f['id'] in actual);files.add(f['id']);checked_file(actual[f['id']],f['content_base64'])
    need(files=={r['id'] for r in actual.values() if r['kind']=='document'})
    messages={}
    for m in obj['team_messages']:
        need(set(m)=={'id','sender_id','recipient_id','body','sent_at'} and type(m['id']) is int and m['id']>0 and m['id'] not in messages);need(m['sender_id'] in people and m['recipient_id'] in people and m['sender_id']!=m['recipient_id']);text(m['body'],4000);need(m['body'].strip());stamp(m['sent_at']);messages[m['id']]=m
    seen=set()
    for r in obj['team_reads']:
        need(set(r)=={'reader_id','peer_id','last_message_id'});key=(r['reader_id'],r['peer_id']);need(key not in seen);seen.add(key);m=messages[r['last_message_id']];need(m['recipient_id']==r['reader_id'] and m['sender_id']==r['peer_id'])
    seen=set()
    for a in obj['team_acks']:
        need(set(a)=={'bulletin_id','version','user_id','acknowledged_at'});key=(a['bulletin_id'],a['version'],a['user_id']);need(key not in seen and a['user_id'] in people);seen.add(key);r=versions[(a['bulletin_id'],a['version'])];need(r['kind']=='bulletin' and r['data']['state']=='published');stamp(a['acknowledged_at'])
    seen=set();sent=set()
    for r in obj['team_requests']:
        need(set(r)=={'actor_id','request_id','payload','result','created_at'});uid(r['actor_id']);uid(r['request_id']);stamp(r['created_at']);key=(r['actor_id'],r['request_id']);need(key not in seen);seen.add(key);p=r['payload'];out=r['result'];need(p['request_id']==r['request_id'] and isinstance(out,dict))
        if p['op']=='send':
            m=out['data'];need(messages[m['id']]==m and m['sender_id']==r['actor_id'] and m['recipient_id']==p['peer_id'] and m['body']==p['body'].strip() and m['id'] not in sent);sent.add(m['id'])
        elif p['op'] in ('profile_save','document_add','document_active','board_save'):
            saved=out['data'];need(versions[(saved['id'],saved['version'])]==saved)
        elif p['op']=='submit_identifiers':need(out=={'submitted':True} and ('intake',r['actor_id']) in unique)
        elif p['op']=='ack_board':need(out=={'acknowledged':True} and any(a['bulletin_id']==p['id'] and a['version']==p['version'] and a['user_id']==r['actor_id'] for a in obj['team_acks']))
        else:raise ValueError('INVALID_TEAM_DATA')
    need(set(messages)==sent)
