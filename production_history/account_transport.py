"""Server-only Auth administration and transactional password email. No request logging."""
import json,os,re,secrets
from urllib import request as http,error
from production_app import PROJECT,NoRedirect,Failure
from admin_controls import gateway_headers
from email_delivery import Settings

class Accounts:
    def __init__(self,publishable):
        self.publishable=publishable
        self.secret=os.getenv('CUSTOMU_AUTH_SECRET_KEY','')
        self.email=Settings()
        self.ready=bool(re.fullmatch(r'sb_secret_[A-Za-z0-9_-]{15,200}',self.secret))
        self.mail_ready=self.ready and os.getenv('CUSTOMU_ACCOUNT_EMAIL_ENABLED')=='1' and self.email.ready
        self.opener=http.build_opener(NoRedirect())

    def call(self,path,body=None,*,method='POST',admin=False,token=None):
        if admin and not self.ready:raise Failure('ACCOUNT_CONFIGURATION_REQUIRED',409)
        key=self.secret if admin else self.publishable
        headers={'apikey':key,'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        if path.startswith('/rest/v1/'):headers.update(gateway_headers())
        req=http.Request(PROJECT+path,headers=headers,data=None if body is None else json.dumps(body).encode(),method=method)
        try:
            with self.opener.open(req,timeout=12) as r:
                raw=r.read(100001)
                if len(raw)>100000:raise Failure('ACCOUNT_PROVIDER_UNCERTAIN')
                parsed=json.loads(raw) if raw else {}
                if not isinstance(parsed,dict):raise Failure('ACCOUNT_PROVIDER_UNCERTAIN')
                return parsed
        except error.HTTPError as e:
            code=e.code;e.close()
            if code==429:raise Failure('PLEASE_WAIT_AND_TRY_AGAIN',429) from None
            if code in (400,401,403,404,422):raise Failure('ACCOUNT_REQUEST_REJECTED',400) from None
            raise Failure('ACCOUNT_PROVIDER_UNCERTAIN') from None
        except (error.URLError,TimeoutError,ValueError,OSError):raise Failure('ACCOUNT_PROVIDER_UNCERTAIN') from None

    def service(self,payload):
        r=self.call('/rest/v1/rpc/custom_u_account_service_119',{'payload':payload},admin=True)
        if 'error' in r:raise Failure(r['error'],400 if r['error']=='PASSWORD_LINK_INVALID' else 403)
        return r

    def create(self,email):
        # Never return, store or send this random password. Employee chooses their own.
        return self.call('/auth/v1/admin/users',{'email':email,'password':secrets.token_urlsafe(48)+'aA1!','email_confirm':True},admin=True)

    def generate(self,email):
        r=self.call('/auth/v1/admin/generate_link',{'type':'recovery','email':email},admin=True)
        token=r.get('hashed_token')
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',token):raise Failure('ACCOUNT_PROVIDER_UNCERTAIN')
        return token

    def verify(self,token):
        return self.call('/auth/v1/verify',{'type':'recovery','token_hash':token})

    def password(self,token,password):
        return self.call('/auth/v1/user',{'password':password},method='PUT',token=token)

    def revoke(self,token):
        self.call('/auth/v1/logout?scope=global',{},token=token)

    def send(self,email,url,ident,purpose):
        if not self.mail_ready:raise Failure('ACCOUNT_EMAIL_NOT_CONFIGURED',409)
        subject='Set up your Custom U password' if purpose=='setup' else 'Reset your Custom U password'
        text=(subject+'\n\nOpen this link and choose your password:\n'+url+
              '\n\nThis link can be used once and expires in 30 minutes. Staff must use an approved computer on an approved network, or have remote permission. Administrators may use mobile.'+
              '\n\nIf you did not expect this email, ignore it. Your password has not changed. Never share this link.\n\nCustom U Business Manager')
        # Password email deliberately never uses the customer-document test recipient.
        body={'from':self.email.sender,'to':[email],'reply_to':self.email.reply_to,'subject':subject,'text':text}
        req=http.Request('https://api.resend.com/emails',data=json.dumps(body).encode(),method='POST',headers={
            'Authorization':'Bearer '+self.email.api_key,'Content-Type':'application/json','Idempotency-Key':'customu-account119/'+ident})
        try:
            with self.opener.open(req,timeout=12) as response:
                raw=response.read(8193)
                r=json.loads(raw) if len(raw)<=8192 else {}
                return 'accepted' if isinstance(r,dict) and isinstance(r.get('id'),str) else 'uncertain'
        except error.HTTPError as e:
            code=e.code;e.close();return 'rejected' if 400<=code<500 and code!=408 else 'uncertain'
        except (error.URLError,TimeoutError,ValueError,OSError):return 'uncertain'
