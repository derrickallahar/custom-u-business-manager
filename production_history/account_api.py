"""Employee creation and password-only recovery; never turn an email link into an app login."""
import hashlib,json,re,uuid,threading
from flask import request,jsonify
from account_transport import Accounts
from admin_controls import client_ip
from device_access import digest as device_digest,mobile

GENERIC='If this is an enabled account, a password email will be sent. Check your inbox and spam folder. If it does not arrive, ask your administrator.'
def sha(value):return hashlib.sha256(value.encode()).hexdigest()

def install(app,provider,session,enabled,root,failure,origin,forget_sessions):
    accounts=Accounts(getattr(provider,'key',''))
    app.extensions['customu_accounts']=accounts
    pending=threading.BoundedSemaphore(4)
    def dispatch(job):
        # Respond identically before lookup/delivery. Bounded background work prevents
        # known-account timing disclosure without an unbounded email-work queue.
        if not pending.acquire(blocking=False):return
        def work():
            try:job()
            except Exception:pass # Never log credentials, provider payloads or recipient details.
            finally:pending.release()
        try:threading.Thread(target=work,daemon=True,name='customu-password-email').start()
        except Exception:pending.release()
    app.extensions['customu_account_dispatch']=dispatch
    def transport():return app.extensions['customu_accounts']
    def fields(names):
        body=request.get_json()
        if not isinstance(body,dict) or set(body)!=set(names):raise failure('INVALID_REQUEST',400)
        return body
    def email(value):
        if not isinstance(value,str) or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value.strip()) or len(value)>254:raise failure('INVALID_REQUEST',400)
        return value.strip().lower()
    def ident(value):
        if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}',value):raise failure('INVALID_REQUEST',400)
        return value
    def password(body):
        value=body['password']
        if not isinstance(value,str) or not 12<=len(value)<=128 or len(value.encode())>256 or value!=body['confirm'] or value.isspace():raise failure('PASSWORD_REQUIREMENTS',400)
        return value
    def admin():
        rec,me=session()
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        return rec,me
    def rpc(rec,payload):
        r=json.loads(provider.call('/rest/v1/rpc/custom_u_employee_accounts_119',rec['token'],{'payload':payload},limit=100000))
        if not isinstance(r,dict):raise failure('ACCOUNT_PROVIDER_UNCERTAIN')
        if 'error' in r:raise failure(r['error'],409)
        return r
    def rate(label,value,count,seconds=3600):
        r=transport().service({'op':'rate','key':label+':'+sha(value),'max':count,'seconds':seconds})
        if r.get('allowed') is not True:raise failure('PLEASE_WAIT_AND_TRY_AGAIN',429)
    def mail(target,purpose,actor=None):
        a=transport()
        if not a.mail_ready:raise failure('ACCOUNT_EMAIL_NOT_CONFIGURED',409)
        rate('mail_global','all',100,86400)
        rate('mail_minute',target['email'].lower(),1,60)
        rate('mail_email',target['email'].lower(),3)
        token=a.generate(target['email']);link_id=str(uuid.uuid4())
        a.service({'op':'issue','id':link_id,'user_id':target['user_id'],'purpose':purpose,'proof':sha(token),'actor_id':actor})
        result=a.send(target['email'],origin+'/password#id='+link_id+'&token='+token,link_id,purpose)
        try:a.service({'op':'delivery','id':link_id,'status':result['delivery']})
        except failure:
            # Keep a confirmed provider rejection distinct from uncertain delivery/history.
            if result['delivery']!='rejected':result={'delivery':'uncertain','reason':'EMAIL_HISTORY_UNCONFIRMED','http_status':None}
        return result
    def audit(user_id,event):
        try:transport().service({'op':'event','user_id':user_id,'event':event})
        except failure:pass # Provider Auth audit is authoritative; never retry a password write.
    def change(token,user_id,new):
        try:
            result=transport().password(token,new)
            if result.get('id')!=user_id:raise failure('ACCOUNT_PROVIDER_UNCERTAIN')
        except failure as e:
            forget_sessions(user_id)
            # A timeout may mean the password changed. Never label it as a confirmed failure.
            if e.status>=500:
                audit(user_id,'password_change_uncertain')
                try:transport().revoke(token)
                except failure:pass
                raise failure('PASSWORD_CHANGE_UNCERTAIN',503) from None
            provider.logout(token)
            raise failure('PASSWORD_NOT_ACCEPTED',400) from None
        forget_sessions(user_id);audit(user_id,'password_changed')
        revoked=True
        try:transport().revoke(token)
        except failure:revoked=False;audit(user_id,'session_revocation_uncertain')
        from production_app import COOKIE
        r=jsonify(changed=True,sessions_revoked=revoked)
        r.delete_cookie(COOKIE,secure=True,httponly=True,samesite='Strict',path='/')
        return r

    @app.get('/account')
    def account_page():return app.response_class((root/'static/account.html').read_bytes(),mimetype='text/html')
    @app.get('/password')
    def password_page():return app.response_class((root/'static/password.html').read_bytes(),mimetype='text/html')
    @app.get('/account.js')
    def account_script():return app.response_class((root/'static/account.js').read_bytes(),mimetype='text/javascript')
    @app.get('/password.js')
    def password_script():return app.response_class((root/'static/password.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/accounts/status')
    def account_status():
        rec,_=admin();installed=False
        try:installed=rpc(rec,{'op':'status'}).get('installed') is True
        except (failure,ValueError):pass
        return jsonify(installed=installed,creation_ready=installed and transport().ready,email_ready=installed and transport().mail_ready)
    @app.post('/api/accounts/create')
    def create_employee():
        rec,me=admin();body=fields(('email','full_name','job_title','request_id'));body['email']=email(body['email']);ident(body['request_id'])
        for k in ('full_name','job_title'):
            if not isinstance(body[k],str) or not body[k].strip() or len(body[k])>254 or re.search(r'[\x00-\x1f\x7f]',body[k]):raise failure('INVALID_REQUEST',400)
            body[k]=body[k].strip()
        if not transport().ready:raise failure('ACCOUNT_CONFIGURATION_REQUIRED',409)
        rate('create',me['user_id'],20)
        found=rpc(rec,{'op':'lookup','email':body['email']})
        if not found.get('user_id'):
            try:transport().create(body['email'])
            except failure:
                # Unique email is the retry key. Read back after an ambiguous create; never reset an existing password.
                found=rpc(rec,{'op':'lookup','email':body['email']})
                if not found.get('user_id'):raise
            found=rpc(rec,{'op':'lookup','email':body['email']})
        if found.get('confirmed') is not True:raise failure('EXISTING_ACCOUNT_NOT_CONFIRMED',409)
        admin() # Recheck the administrator before granting even disabled membership.
        result=rpc(rec,{'op':'attach',**body})
        return jsonify(result)
    @app.post('/api/accounts/send-setup')
    def send_setup():
        rec,me=admin();body=fields(('user_id',));ident(body['user_id'])
        target=rpc(rec,{'op':'target','user_id':body['user_id']})
        result=mail(target,'setup',me['user_id'])
        return jsonify(**result,email=target['email'])
    @app.post('/api/password/forgot')
    def forgot():
        body=fields(('email',));address=email(body['email'])
        ip=client_ip() or 'unverified'
        def work():
            try:
                if not transport().mail_ready:raise failure('ACCOUNT_EMAIL_NOT_CONFIGURED')
                # Unknown ingress shares one strict bucket; never trust X-Forwarded-For.
                rate('forgot_ip',ip,20)
                rate('forgot_global','all',200)
                target=transport().service({'op':'lookup','email':address})
                if target.get('eligible') is True:mail(target,'recovery')
            except failure:pass
        app.extensions['customu_account_dispatch'](work)
        return jsonify(message=GENERIC),202
    @app.post('/api/password/reset')
    def reset():
        body=fields(('id','token','password','confirm','mobile'));ident(body['id']);new=password(body)
        if type(body['mobile']) is not bool or not isinstance(body['token'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',body['token']):raise failure('INVALID_REQUEST',400)
        rate('reset_ip',client_ip() or 'unverified',30)
        gate=transport().service({'op':'claim','id':body['id'],'proof':sha(body['token']),'device_digest':device_digest(),'mobile':mobile(body['mobile'])})
        try:result=transport().verify(body['token'])
        except failure:raise failure('PASSWORD_LINK_INVALID',400) from None
        token=result.get('access_token');user=result.get('user',{})
        if not isinstance(token,str) or not token or len(token)>20000 or user.get('id')!=gate.get('user_id'):
            if isinstance(token,str):provider.logout(token)
            raise failure('PASSWORD_LINK_INVALID',400)
        # Check the live account and restrictions again after Auth creates the recovery session.
        try:
            me=provider.access(token)
            if me.get('user_id')!=gate['user_id']:raise failure('ACCESS_DENIED',403)
            from device_access import authorize
            authorize(provider,{'token':token},me,failure,body['mobile'])
        except Exception:provider.logout(token);raise
        return change(token,gate['user_id'],new)
    @app.post('/api/account/password')
    def change_password():
        rec,me=session();body=fields(('current','password','confirm'));new=password(body)
        if not isinstance(body['current'],str) or not 1<=len(body['current'])<=128:raise failure('INVALID_REQUEST',400)
        rate('change',me['user_id'],10)
        try:auth=provider.login(me['email'],body['current'])
        except failure:raise failure('CURRENT_PASSWORD_INCORRECT',400) from None
        token=auth.get('access_token')
        if not isinstance(token,str) or not token or len(token)>20000:raise failure('ACCOUNT_PROVIDER_UNCERTAIN')
        try:
            fresh=provider.access(token)
            if fresh.get('user_id')!=me['user_id']:raise failure('ACCESS_DENIED',403)
            from device_access import authorize
            authorize(provider,{'token':token},fresh,failure)
            session()
        except Exception:provider.logout(token);raise
        return change(token,me['user_id'],new)
