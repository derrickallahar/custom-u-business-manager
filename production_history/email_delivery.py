"""Private Resend transport and short-lived, session-bound review tokens.

There are deliberately no automatic retries, background sends or delivery claims.
An accepted response means Resend accepted the request, not inbox delivery.
"""
import base64,hashlib,hmac,json,os,re,time
from urllib import request as http,error

MAX_PDF=1500000
EMAIL=re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+",re.I)
UID=re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def address(v):
    if not isinstance(v,str):raise ValueError('EMAIL_RECIPIENT_INVALID')
    v=v.strip().lower()
    if not 3<=len(v)<=254 or not EMAIL.fullmatch(v) or len(v.split('@')[0])>64 or '..' in v.split('@')[0] or v.startswith('.') or v.split('@')[0].endswith('.'):raise ValueError('EMAIL_RECIPIENT_INVALID')
    return v
def clean(v,limit,single=False):
    if not isinstance(v,str) or not 1<=len(v.strip())<=limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',v) or single and re.search(r'[\r\n]',v):raise ValueError('EMAIL_FIELDS_INVALID')
    return v.strip()
def identifier(v):
    if not isinstance(v,str) or not UID.fullmatch(v):raise ValueError('INVALID_REQUEST')
    return v
def checked_pdf(row):
    try:
        raw=base64.b64decode(row['pdf_base64'],validate=True)
        if not 20<=len(raw)<=MAX_PDF or not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest()!=row['pdf_sha256']:raise ValueError()
        if not re.fullmatch(r'CustomU_[A-Za-z0-9_-]{1,100}\.pdf',row['pdf_filename']):raise ValueError()
        return raw
    except (ValueError,TypeError,KeyError):raise ValueError('EMAIL_PDF_INVALID') from None

class Settings:
    def __init__(self):
        self.api_key=os.getenv('RESEND_API_KEY','')
        self.secret=os.getenv('CUSTOMU_EMAIL_SIGNING_SECRET','')
        self.test_mode=os.getenv('CUSTOMU_EMAIL_TEST_MODE','1')!='0'
        self.test_to=address(os.getenv('CUSTOMU_EMAIL_TEST_RECIPIENT','derrick@custom-u.com'))
        self.from_email=address(os.getenv('CUSTOMU_EMAIL_FROM','documents@updates.custom-u.com'))
        if self.from_email.split('@')[1]!='updates.custom-u.com':raise ValueError('EMAIL_FROM_DOMAIN_INVALID')
        self.sender='Custom U <'+self.from_email+'>'
        self.reply_to=address(os.getenv('CUSTOMU_EMAIL_REPLY_TO','derrick@custom-u.com'))
    @property
    def ready(self):return bool(re.fullmatch(r're_[A-Za-z0-9_-]{10,200}',self.api_key) and re.fullmatch('[a-f0-9]{64}',self.secret))
    def signature(self,purpose,message):return hmac.new(bytes.fromhex(self.secret),(purpose+'109\n'+message).encode(),hashlib.sha256).hexdigest()
    def signed_rpc(self,payload,actor):
        message=canonical({'payload':payload,'actor_id':identifier(actor),'expires':int(time.time())+90})
        return {'op':'signed','message':message,'signature':self.signature('rpc',message)}
    def review(self,data,token):
        message=canonical({**data,'session':hashlib.sha256(token.encode()).hexdigest(),'expires':int(time.time())+600})
        return base64.urlsafe_b64encode(message.encode()).decode()+'.'+self.signature('review',message)
    def read_review(self,value,token):
        try:
            if not isinstance(value,str) or len(value)>20000:raise ValueError()
            encoded,sig=value.split('.');message=base64.b64decode(encoded,altchars=b'-_',validate=True).decode()
            if not hmac.compare_digest(sig,self.signature('review',message)):raise ValueError()
            data=json.loads(message)
            if data['session']!=hashlib.sha256(token.encode()).hexdigest() or type(data['expires']) is not int or not time.time()<=data['expires']<=time.time()+610:raise ValueError()
            return data
        except (ValueError,TypeError,KeyError):raise ValueError('EMAIL_REVIEW_EXPIRED') from None

class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Resend:
    def __init__(self,key):self.key=key;self.opener=http.build_opener(NoRedirect())
    def send(self,row):
        checked_pdf(row)
        body={'from':row['sender'],'to':[row['recipient']],'reply_to':row['reply_to'],'subject':row['subject'],'text':row['message'],'attachments':[{'filename':row['pdf_filename'],'content':row['pdf_base64']}]}
        req=http.Request('https://api.resend.com/emails',data=canonical(body).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json','Idempotency-Key':'customu109/'+row['id'],'User-Agent':'CustomU/109'},method='POST')
        try:
            with self.opener.open(req,timeout=20) as response:
                raw=response.read(16385)
                if len(raw)>16384:return ('uncertain',None,'EMAIL_RESPONSE_INVALID')
                value=json.loads(raw)
                if not isinstance(value,dict) or not isinstance(value.get('id'),str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',value['id']):return ('uncertain',None,'EMAIL_RESPONSE_INVALID')
                return ('accepted',value['id'],None)
        except error.HTTPError as exc:
            status=exc.code;exc.close()
            return ('rejected' if status in (400,401,403,404,413,422,429) else 'uncertain',None,'EMAIL_PROVIDER_HTTP_'+str(status))
        except (error.URLError,TimeoutError,OSError,ValueError):return ('uncertain',None,'EMAIL_PROVIDER_UNCERTAIN')
