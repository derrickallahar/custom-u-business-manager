"""Private history, administrator CRM, saved quotes, invoices and manual payment records."""
import hashlib, hmac, json, os, re, secrets, threading, time
from pathlib import Path
from urllib import request as http, error
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, make_response
from werkzeug.exceptions import HTTPException

PROJECT='https://ldzugsrflgrlxmntbqtc.supabase.co'
BUCKET='custom-u-history'
COOKIE='__Host-customu_history_091'
ROOT=Path(__file__).resolve().parent

class Failure(Exception):
    def __init__(self,code,status=503):self.code=code;self.status=status

class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Supabase:
    def __init__(self,key):
        if not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]+',key):raise ValueError('PRODUCTION_PUBLISHABLE_KEY_REQUIRED')
        self.key=key
        self.opener=http.build_opener(NoRedirect())
    def call(self,path,token=None,body=None,limit=100000):
        headers={'apikey':self.key,'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=http.Request(PROJECT+path,headers=headers,data=None if body is None else json.dumps(body).encode(),method='GET' if body is None else 'POST')
        try:
            with self.opener.open(req,timeout=12) as r:
                data=r.read(limit+1)
                if len(data)>limit:raise Failure('RESPONSE_TOO_LARGE')
                return data
        except error.HTTPError as e:
            status=e.code;e.close()
            if status==429:raise Failure('PLEASE_WAIT_AND_TRY_AGAIN',429) from None
            if status in (400,401,403):raise Failure('SIGN_IN_OR_ACCESS_REJECTED',401) from None
            raise Failure('PROVIDER_REQUEST_FAILED') from None
        except (error.URLError,TimeoutError):raise Failure('PROVIDER_UNAVAILABLE') from None
    def login(self,email,password):
        return json.loads(self.call('/auth/v1/token?grant_type=password',body={'email':email,'password':password}))
    def access(self,token):
        user=json.loads(self.call('/auth/v1/user',token))
        member=json.loads(self.call('/rest/v1/rpc/custom_u_history_access_091',token,{}))
        if not isinstance(member,dict) or member.get('user_id')!=user.get('id') or member.get('role')!='admin' or member.get('bucket_private') is not True:
            raise Failure('ACCESS_DENIED',403)
        return {'email':user.get('email',''),'role':'admin'}
    def archive(self,token,digest):
        return self.call('/storage/v1/object/authenticated/'+BUCKET+'/history091/'+digest+'.json',token,limit=10000000)
    def logout(self,token):
        try:self.call('/auth/v1/logout?scope=local',token,{})
        except Failure:pass

def create_app(provider=None,origin=None,digest=None,crm_enabled=None):
    crm_enabled = os.getenv("CUSTOMU_PRODUCTION_CRM_ENABLED", "") == "1" if crm_enabled is None else crm_enabled
    origin=(origin or os.getenv('CUSTOMU_PRODUCTION_ORIGIN','')).rstrip('/')
    parts=urlsplit(origin)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment or not re.fullmatch(r'[A-Za-z0-9.-]+(?::443)?',parts.netloc):
        raise ValueError('PRODUCTION_HTTPS_ORIGIN_REQUIRED')
    if parts.hostname=='oyster-app-ami87.ondigitalocean.app':
        raise ValueError('USE_A_SEPARATE_PRODUCTION_SERVICE')
    provider=provider or Supabase(os.getenv('CUSTOMU_PRODUCTION_PUBLISHABLE_KEY',''))
    digest=os.getenv('CUSTOMU_PRODUCTION_HISTORY_SHA256','') if digest is None else digest
    if digest and not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('ARCHIVE_DIGEST_INVALID')
    app=Flask(__name__,static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=4096)
    lock=threading.Lock();sessions={};attempts=[];archive_lock=threading.Lock();loaded=[]
    app.extensions['customu_sessions']=sessions
    def session():
        sid=request.cookies.get(COOKIE,'')
        with lock:
            rec=sessions.get(hashlib.sha256(sid.encode()).hexdigest())
            if not rec or rec['expires']<=time.time():
                if rec:sessions.pop(hashlib.sha256(sid.encode()).hexdigest(),None)
                raise Failure('LOGIN_REQUIRED',401)
        me=provider.access(rec['token'])
        return rec,me
    def archive(rec):
        if not digest:raise Failure('HISTORY_IMPORT_PENDING',409)
        with archive_lock:
            if not loaded:
                from archive_reader import Reader
                raw=provider.archive(rec['token'],digest)
                if hashlib.sha256(raw).hexdigest()!=digest:raise Failure('ARCHIVE_CHECKSUM_FAILED')
                loaded.append(Reader(raw))
            return loaded[0]
    @app.before_request
    def check_request():
        if request.path=='/healthz' and request.method=='GET':return None
        if request.host.lower()!=parts.netloc.lower():raise Failure('INVALID_HOST',403)
        if request.method not in ('GET','HEAD','POST'):raise Failure('METHOD_NOT_ALLOWED',405)
        if request.method=='POST':
            if request.headers.get('Origin')!=origin or request.mimetype!='application/json':raise Failure('INVALID_ORIGIN_OR_CONTENT_TYPE',403)
        elif request.headers.get('Origin') not in (None,origin):raise Failure('INVALID_ORIGIN',403)
    @app.after_request
    def headers(r):
        r.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Vary':'Cookie','Strict-Transport-Security':'max-age=31536000',
          'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
          'X-Robots-Tag':'noindex, nofollow','Cross-Origin-Resource-Policy':'same-origin'})
        return r
    @app.errorhandler(Failure)
    def fail(e):return jsonify(error=e.code),e.status
    @app.errorhandler(HTTPException)
    def http_error(e):return jsonify(error='REQUEST_REJECTED'),e.code
    @app.errorhandler(Exception)
    def unexpected(e):return jsonify(error='REQUEST_FAILED'),503
    @app.get('/healthz')
    def health():return jsonify(status='ok',service='production-payments-099')
    @app.get('/')
    def index():return app.response_class((ROOT/'static/index.html').read_bytes(),mimetype='text/html')
    @app.get('/app.js')
    def javascript():return app.response_class((ROOT/'static/app.js').read_bytes(),mimetype='text/javascript')
    @app.post('/api/login')
    def login():
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'email','password'}:raise Failure('INVALID_LOGIN_REQUEST',400)
        email=data['email'];password=data['password']
        if not isinstance(email,str) or not 3<=len(email)<=254 or not isinstance(password,str) or not 1<=len(password)<=128:raise Failure('INVALID_LOGIN_REQUEST',400)
        with lock:
            now=time.time();attempts[:]=[t for t in attempts if t>now-60]
            if len(attempts)>=20:raise Failure('PLEASE_WAIT_AND_TRY_AGAIN',429)
            attempts.append(now)
        result=provider.login(email.strip(),password)
        token=result['access_token']
        if not isinstance(token,str) or len(token)>20000:raise Failure('INVALID_PROVIDER_RESPONSE')
        try:me=provider.access(token)
        except Exception:
            provider.logout(token);raise
        ttl=max(1,min(3600,int(result['expires_in'])))
        sid=secrets.token_urlsafe(48);key=hashlib.sha256(sid.encode()).hexdigest()
        old=request.cookies.get(COOKIE,'')
        with lock:
            for k in [k for k,r in sessions.items() if r['expires']<=time.time()]:sessions.pop(k)
            if len(sessions)>=100:raise Failure('SESSION_CAPACITY_REACHED',429)
            sessions.pop(hashlib.sha256(old.encode()).hexdigest(),None)
            sessions[key]={'token':token,'expires':time.time()+ttl}
        r=jsonify(me=me,archive_configured=bool(digest),crm_enabled=bool(crm_enabled))
        r.set_cookie(COOKIE,sid,secure=True,httponly=True,samesite='Strict',max_age=ttl,path='/')
        return r
    @app.post('/api/logout')
    def logout():
        key=hashlib.sha256(request.cookies.get(COOKIE,'').encode()).hexdigest()
        with lock:rec=sessions.pop(key,None)
        if rec:provider.logout(rec['token'])
        r=jsonify(signed_out=True);r.delete_cookie(COOKIE,secure=True,httponly=True,samesite='Strict',path='/');return r
    @app.get('/api/session')
    def who():
        _,me=session();return jsonify(me=me,archive_configured=bool(digest),crm_enabled=bool(crm_enabled))
    @app.get('/api/history')
    def listing():
        rec,_=session();return jsonify(archive(rec).listing(request.query_string.decode('utf-8')))
    @app.get('/api/history/records/<ident>')
    def detail(ident):
        rec,_=session();return jsonify(data=archive(rec).detail(ident))
    @app.get('/api/history/files/<ident>')
    def pdf(ident):
        rec,_=session();name,blob=archive(rec).pdf(ident)
        r=make_response(blob);r.headers['Content-Type']='application/pdf';r.headers['Content-Disposition']='attachment; filename="'+name+'"';return r
    from crm_api import install
    install(app,provider,session,crm_enabled,ROOT,Failure)
    from backup_api import install as install_backup
    install_backup(app,provider,session,crm_enabled,Failure)
    from import_api import install as install_import
    install_import(app,provider,session,crm_enabled,ROOT,Failure)
    install_import(app,provider,session,crm_enabled,ROOT,Failure,reviewed=True)
    from quote_api import install as install_quotes
    install_quotes(app,provider,session,crm_enabled,ROOT,Failure)
    from invoice_api import install as install_invoices
    install_invoices(app,provider,session,crm_enabled,ROOT,Failure)
    from payment_api import install as install_payments
    install_payments(app,provider,session,crm_enabled,ROOT,Failure)
    return app
