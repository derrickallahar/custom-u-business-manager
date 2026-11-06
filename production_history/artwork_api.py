"""Session-bound immutable artwork transport, integrity checks and encrypted bundles."""
import base64,hashlib,io,json,re,threading,time,zipfile
from flask import request,jsonify,make_response
from staff_access import can
from workspace_codec import parse,passphrase_bytes
from artwork_codec import encrypt
MAX_FILE=6000000
BUCKET='custom-u-artwork-104'
UUID=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _().-]*\.(pdf|png|jpg|jpeg|svg|ai|eps|psd|tif|tiff|cdr)$')
def permitted(me,cap):return can(me,'jobs.view') and can(me,'artwork.view') and can(me,cap)

def install(app,provider,session,enabled,root,failure):
    def gate(cap='artwork.view',admin=False):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not permitted(me,cap) or admin and me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec
    def check(rec,cap='artwork.view',admin=False):
        me=provider.access(rec['token'])
        if not permitted(me,cap) or admin and me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
    def rpc(rec,payload,cap='artwork.view'):
        r=parse(provider.call('/rest/v1/rpc/custom_u_artwork_104',rec['token'],{'payload':payload},limit=2*1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'ARTWORK_JOB_LOCKED':409}.get(r['error'],400))
        check(rec,cap);return r
    def identity(job,ident=None):
        if not isinstance(job,str) or not UUID.fullmatch(job) or ident is not None and (not isinstance(ident,str) or not UUID.fullmatch(ident)):raise failure('INVALID_ID',400)
    def bytes_for(rec,f):
        identity(f['job_id'],f['id'])
        if f['object_path']!=f['job_id']+'/'+f['id']:raise failure('INVALID_PROVIDER_RESPONSE')
        raw=provider.artwork_blob(f['object_path'],rec['token'])
        if len(raw)!=f['size_bytes'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:raise failure('FILE_INTEGRITY_FAILED',409)
        return raw
    def download(raw,name):
        r=make_response(raw);r.headers['Content-Type']='application/octet-stream';r.headers['Content-Disposition']='attachment; filename="'+name+'"';return r
    @app.get('/artwork/<job>')
    def artwork_page(job):
        identity(job);return app.response_class((root/'static/artwork.html').read_bytes(),mimetype='text/html')
    @app.get('/artwork.js')
    def artwork_script():return app.response_class((root/'static/artwork.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/artwork/<job>')
    def artwork_listing(job):
        identity(job);rec=gate();return jsonify(rpc(rec,{'op':'list','job_id':job}))
    @app.get('/api/artwork/<job>/<ident>/download')
    def artwork_file_download(job,ident):
        identity(job,ident);rec=gate();f=rpc(rec,{'op':'get','job_id':job,'id':ident})['data'];raw=bytes_for(rec,f);check(rec)
        if not isinstance(f['filename'],str) or len(f['filename'])>160 or not NAME.fullmatch(f['filename']):raise failure('INVALID_PROVIDER_RESPONSE')
        return download(raw,'v'+str(f['version'])+'_'+f['filename'])
    upload_lock=threading.Lock()
    @app.post('/api/artwork/<job>/upload')
    def artwork_upload(job):
        identity(job);rec=gate('artwork.upload');request.max_content_length=8100000
        if not upload_lock.acquire(blocking=False):raise failure('UPLOAD_BUSY',429)
        try:
            body=request.get_json()
            if not isinstance(body,dict) or set(body)!={'id','filename','data'} or not isinstance(body.get('id'),str) or not UUID.fullmatch(body['id']) or not isinstance(body['filename'],str) or len(body['filename'])>160 or not NAME.fullmatch(body['filename']) or not isinstance(body['data'],str) or len(body['data'])>8000000:raise failure('INVALID_FILE',400)
            try:raw=base64.b64decode(body['data'],validate=True)
            except (ValueError,TypeError):raise failure('INVALID_FILE',400) from None
            if not 1<=len(raw)<=MAX_FILE:raise failure('FILE_SIZE_LIMIT',400)
            f=rpc(rec,{'op':'reserve','job_id':job,'id':body['id'],'filename':body['filename'],'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'artwork.upload')['data']
            if f['status']!='stored':
                # Only duplicate/uncertain uploads may be recovered by reading back
                # the same reserved path. A definite rejection is not a lost reply.
                upload_error=None
                try:provider.artwork_blob(f['object_path'],rec['token'],raw)
                except failure as e:
                    if e.code not in ('ARTWORK_OBJECT_EXISTS','ARTWORK_UPLOAD_UNCERTAIN','PROVIDER_UNAVAILABLE'):raise
                    upload_error=e
                try:bytes_for(rec,f)
                except failure as e:
                    if e.code=='FILE_INTEGRITY_FAILED':raise
                    if upload_error and upload_error.code!='ARTWORK_OBJECT_EXISTS':raise upload_error from None
                    if e.code=='FILE_UNAVAILABLE':raise failure('ARTWORK_VERIFY_UNAVAILABLE',409) from None
                    raise
                r=rpc(rec,{'op':'store','job_id':job,'id':f['id']},'artwork.upload')
            else:bytes_for(rec,f);r={'data':f,'existing':True}
            check(rec,'artwork.upload');return jsonify(r)
        finally:upload_lock.release()
    @app.post('/api/artwork/<job>/approval')
    def artwork_approval(job):
        identity(job);rec=gate('artwork.approve');body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('approve','unapprove') or body.get('job_id')!=job:raise failure('INVALID_REQUEST',400)
        if body['op']=='approve':
            identity(job,body.get('id',''));f=rpc(rec,{'op':'get','job_id':job,'id':body['id']})['data'];bytes_for(rec,f)
        return jsonify(rpc(rec,body,'artwork.approve'))
    backup_lock=threading.Lock();last={}
    @app.post('/api/artwork/<job>/backup')
    def artwork_backup(job):
        identity(job);rec=gate(admin=True);body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'passphrase'}:raise failure('INVALID_REQUEST',400)
        try:passphrase_bytes(body['passphrase'])
        except ValueError:raise failure('PASSPHRASE_LENGTH',400) from None
        if not backup_lock.acquire(blocking=False):raise failure('BACKUP_BUSY',429)
        try:
            now=time.monotonic()
            if now-last.get('at',-100)<30:raise failure('BACKUP_WAIT_30_SECONDS',429)
            last['at']=now
            manifest=rpc(rec,{'op':'list','job_id':job});manifest['format']='custom-u-artwork-bundle-104'
            files=[f for f in manifest['files'] if f['status']=='stored']
            if not files:raise failure('NO_STORED_FILES',400)
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
                z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
                for f in files:z.writestr('files/'+f['id']+'.'+f['filename'].rsplit('.',1)[1],bytes_for(rec,f))
            # Do not label a moving target as a completed backup.
            again=rpc(rec,{'op':'list','job_id':job})
            if any(again[k]!=manifest[k] for k in ('files','head','audit')):raise failure('BACKUP_CHANGED_RETRY',409)
            check(rec,admin=True);blob=encrypt(buf.getvalue(),body['passphrase'])
            return download(blob,'CustomU_Artwork_104_'+job+'_'+hashlib.sha256(blob).hexdigest()[:8]+'.cuart')
        finally:body=None;backup_lock.release()
