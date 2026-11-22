"""Validate immutable artwork versions and the complete approval revision chain."""
import re
from recover_crm import require,uid,date
FILE_FIELDS={'id','job_id','version','filename','size_bytes','sha256','object_path','status','created_by','created_at','stored_at'}
HEAD_FIELDS={'job_id','revision','approved_id','reference','updated_by','updated_at'}
def file_record(f):
    require(isinstance(f,dict) and set(f)==FILE_FIELDS);uid(f['id']);uid(f['job_id']);uid(f['created_by']);date(f['created_at'])
    require(type(f['version']) is int and 1<=f['version']<=50 and type(f['size_bytes']) is int and 1<=f['size_bytes']<=6000000)
    require(isinstance(f['filename'],str) and len(f['filename'])<=160 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _().-]*\.(pdf|png|jpg|jpeg|svg|ai|eps|psd|tif|tiff|cdr)',f['filename']))
    require(isinstance(f['sha256'],str) and re.fullmatch('[0-9a-f]{64}',f['sha256']) and f['object_path']==f['job_id']+'/'+f['id'])
    require(f['status'] in ('pending','stored'))
    if f['status']=='pending':require(f['stored_at'] is None)
    else:require(date(f['stored_at'])>=date(f['created_at']))
def head_record(h,files):
    require(isinstance(h,dict) and set(h)==HEAD_FIELDS);uid(h['job_id']);uid(h['updated_by']);date(h['updated_at']);require(type(h['revision']) is int and h['revision']>0)
    require(isinstance(h['reference'],str) and h['reference']==h['reference'].strip() and len(h['reference'])<=300 and all(ord(c)>=32 and ord(c)!=127 for c in h['reference']))
    if h['approved_id'] is not None:
        uid(h['approved_id']);f=files[h['approved_id']];require(f['job_id']==h['job_id'] and f['status']=='stored' and len(h['reference'])>=3)
def validate_artwork(files,heads,audit):
    require(isinstance(files,list) and len(files)<=2000 and isinstance(heads,list) and isinstance(audit,list) and len(audit)<=100000)
    records={};versions={};sizes={}
    for f in files:
        file_record(f);require(f['id'] not in records);records[f['id']]=f;versions.setdefault(f['job_id'],[]).append(f['version']);sizes[f['job_id']]=sizes.get(f['job_id'],0)+f['size_bytes']
    for j,vs in versions.items():require(sorted(vs)==list(range(1,len(vs)+1)) and sizes[j]<=40000000)
    head_records={}
    for h in heads:head_record(h,records);require(h['job_id'] not in head_records);head_records[h['job_id']]=h
    current_files={};current_heads={};seen=set();approved_revisions={}
    for a in sorted(audit,key=lambda r:r.get('id',0) if isinstance(r,dict) and type(r.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id','job_id','actor_id','happened_at','operation','file_id','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['job_id']);uid(a['actor_id']);date(a['happened_at'])
        j=a['job_id'];b=a['before_record'];r=a['after_record'];op=a['operation'];require(isinstance(r,dict) and set(r)=={'file','head'})
        f=r['file'];h=r['head'];oldh=current_heads.get(j)
        if op=='reserve':
            require(b is None);file_record(f);require(f['job_id']==j and f['id']==a['file_id'] and f['id'] not in current_files and f['status']=='pending' and f['created_by']==a['actor_id'] and f['created_at']==a['happened_at'] and h==oldh);current_files[f['id']]=f
        else:
            require(op in ('store','approve','unapprove') and isinstance(b,dict) and set(b)=={'file','head'} and b['head']==oldh)
            if op=='store':
                file_record(f);require(f['id']==a['file_id'] and f['job_id']==j and b['file']==current_files.get(f['id']) and b['file']['status']=='pending' and f['status']=='stored' and f['stored_at']==a['happened_at'] and f['created_by']==a['actor_id'])
                require({k:v for k,v in b['file'].items() if k not in ('status','stored_at')}=={k:v for k,v in f.items() if k not in ('status','stored_at')});current_files[f['id']]=f
            else:require(f is None and b['file'] is None and oldh is not None)
            head_record(h,current_files);require(h['job_id']==j and h['updated_by']==a['actor_id'] and h['updated_at']==a['happened_at'] and h['revision']==(oldh['revision'] if oldh else 0)+1)
            if op=='approve':require(h['approved_id']==a['file_id'] and h['approved_id'] is not None);approved_revisions[(j,h['revision'])]=h
            else:require(h['approved_id'] is None)
            if op=='store':require(h['reference']=='')
            if op=='unapprove':require(a['file_id'] is None and len(h['reference'])>=3)
            current_heads[j]=h
    require(current_files==records and current_heads==head_records)
    return approved_revisions

def validate_workspace_artwork(obj):
    revisions=validate_artwork(obj['artwork_files'],obj['artwork_heads'],obj['artwork_audit']);jobs={j['id']:j for j in obj['jobs']};members={m['user_id'] for m in obj['staff_members']}
    for f in obj['artwork_files']:require(f['job_id'] in jobs and f['created_by'] in members)
    for h in obj['artwork_heads']:require(h['job_id'] in jobs and h['updated_by'] in members)
    for a in obj['artwork_audit']:require(a['job_id'] in jobs and a['actor_id'] in members)
    for a in obj['job_audit']:
        g=a['after_record']['release_check']
        if g and 'artwork_file_id' in g:
            h=revisions[(a['job_id'],g['artwork_revision'])];require(h['approved_id']==g['artwork_file_id'] and date(h['updated_at'])<=date(g['checked_at']))
