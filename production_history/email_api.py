"""Explicit review then send. Persist a single attempt before any provider call."""
import base64,hashlib,uuid
from flask import request,jsonify,make_response
from reportlab.platypus.doctemplate import LayoutError
from staff_access import can
from workspace_codec import parse
from email_delivery import Settings,Resend,address,clean,identifier,checked_pdf,canonical,MAX_PDF
from document_pdf import render_document
from catalogue_pdf import render_catalogue

AREAS={'quote':'quotes','invoice':'invoices','catalogue':'products'}
def permitted(me,kind,write=False):
    area=AREAS.get(kind) if isinstance(kind,str) else None
    return bool(area and can(me,area+'.view') and (kind!='catalogue' or can(me,'customers.view')) and (not write or can(me,area+'.send')))

def install(app,provider,session,enabled,root,failure):
    try:config=Settings()
    except ValueError:config=None
    transport=Resend(config.api_key) if config and config.ready else None
    app.extensions['email_transport']=transport
    memory_lock=app.extensions['catalogue_memory_lock']
    def gate(kind,write=False):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not permitted(me,kind,write):raise failure('ACCESS_DENIED',403)
        return rec,me
    def checked(rec,kind,write=False):
        me=provider.access(rec['token'])
        if not permitted(me,kind,write):raise failure('ACCESS_DENIED',403)
        return me
    def call(rec,payload,signed=False,me=None):
        if signed:
            if not config or not config.ready:raise failure('EMAIL_NOT_CONFIGURED',409)
            payload=config.signed_rpc(payload,(me or provider.access(rec['token'])).get('user_id',''))
        result=parse(provider.call('/rest/v1/rpc/custom_u_email_109',rec['token'],{'payload':payload},limit=2200000))
        if not isinstance(result,dict):raise failure('EMAIL_RECORD_UNCERTAIN',503)
        if result.get('error'):raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 404 if result['error']=='NOT_FOUND' else 409)
        return result
    def source(rec,kind,ident,pdf=False):
        endpoint={'quote':'custom_u_quotes_097','invoice':'custom_u_invoices_098','catalogue':'custom_u_client_catalogues_108'}[kind]
        result=parse(provider.call('/rest/v1/rpc/'+endpoint,rec['token'],{'payload':{'op':'document' if kind=='catalogue' and pdf else 'get','id':ident}},limit=9000000))
        if not isinstance(result,dict) or not isinstance(result.get('data'),dict):raise failure(result.get('error','INVALID_PROVIDER_RESPONSE') if isinstance(result,dict) else 'INVALID_PROVIDER_RESPONSE',409)
        r=result['data'];checked(rec,kind,pdf)
        ready=r.get('active') is True if kind=='catalogue' else r.get('status')=='issued'
        if pdf and not ready:raise failure('EMAIL_DOCUMENT_NOT_READY',409)
        if not pdf:return r,ready,None
        try:raw=render_catalogue(r,result['assets']) if kind=='catalogue' else render_document(kind,r)
        except (ValueError,KeyError,TypeError,LayoutError):raise failure('EMAIL_PDF_INVALID',409) from None
        if len(raw)>MAX_PDF:raise failure('EMAIL_PDF_TOO_LARGE',409)
        return r,ready,raw
    def values():
        request.max_content_length=24000
        data=request.get_json()
        if not isinstance(data,dict):raise failure('INVALID_REQUEST',400)
        return data
    def valid(fn,*args):
        try:return fn(*args)
        except ValueError as exc:raise failure(str(exc),400) from None
    def output(row):return {k:v for k,v in row.items() if k!='pdf_base64'}
    @app.get('/email')
    def email_page():return app.response_class((root/'static/email.html').read_bytes(),mimetype='text/html')
    @app.get('/email.js')
    def email_script():return app.response_class((root/'static/email.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/email/context')
    def email_context():
        kind=request.args.get('kind');ident=valid(identifier,request.args.get('id'));rec,me=gate(kind)
        r,ready,_=source(rec,kind,ident)
        q=r.get('quote_snapshot',r);contact=q.get('contact_snapshot') or {};buyer=q.get('customer_snapshot') or {}
        test=bool(not config or config.test_mode or kind=='invoice' and r.get('is_test'))
        number=r.get('number',r.get('title','Catalogue'))
        configured=False
        if config and config.ready:
            try:configured=call(rec,{'op':'health'},True,me).get('ready') is True
            except failure:pass
        checked(rec,kind)
        return jsonify(kind=kind,id=ident,number=number,version=r['version'],ready=ready,send_allowed=permitted(me,kind,True),configured=configured,test_delivery=test,
          recipient=(config.test_to if config else '') if test else contact.get('email') or buyer.get('email') or '',sender=config.sender if config else '',reply_to=config.reply_to if config else '',
          subject=('TEST - ' if test else '')+'Custom U '+kind.title()+': '+number,
          message='Hello,\n\nPlease find your '+kind+' attached for review.\n\nKind regards,\nCustom U',test_recipient=config.test_to if config else '')
    @app.get('/api/email/history')
    def email_history():
        kind=request.args.get('kind');rec,_=gate(kind);ident=valid(identifier,request.args.get('id'))
        result=call(rec,{'op':'list','kind':kind,'document_id':ident});checked(rec,kind);return jsonify(result)
    @app.get('/api/email/<ident>/pdf')
    def email_pdf(ident):
        rec,_=session();valid(identifier,ident)
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        row=call(rec,{'op':'get','id':ident})['data'];checked(rec,row['kind']);raw=valid(checked_pdf,row)
        r=make_response(raw);r.headers['Content-Type']='application/pdf';r.headers['Content-Disposition']='inline; filename="'+row['pdf_filename']+'"';return r
    @app.post('/api/email/preview')
    def email_preview():
        data=values()
        if set(data)!={'kind','id','recipient','subject','message'}:raise failure('INVALID_REQUEST',400)
        kind=data['kind'];rec,me=gate(kind,True)
        if not config or not config.ready:raise failure('EMAIL_NOT_CONFIGURED',409)
        ident=valid(identifier,data['id']);to=valid(address,data['recipient']);subject=valid(clean,data['subject'],160,True);message=valid(clean,data['message'],3900)
        call(rec,{'op':'health'},True,me)
        if not memory_lock.acquire(False):raise failure('EMAIL_PREVIEW_BUSY',429)
        try:r,_,raw=source(rec,kind,ident,True)
        finally:memory_lock.release()
        test=config.test_mode or kind=='invoice' and r.get('is_test',False)
        if test and to!=config.test_to:raise failure('EMAIL_TEST_RECIPIENT_ONLY',409)
        if test:
            if not subject.startswith('TEST - '):subject='TEST - '+subject
            message='TEST DELIVERY - for internal checking only.\n\n'+message
        subject=valid(clean,subject,160,True);number=r.get('number',r.get('title','Catalogue'))
        packet={'id':str(uuid.uuid4()),'kind':kind,'document_id':ident,'document_version':r['version'],'document_number':number,'recipient':to,'subject':subject,'message':message,'sender':config.sender,'reply_to':config.reply_to,'test_delivery':bool(test),'pdf_sha256':hashlib.sha256(raw).hexdigest(),'pdf_filename':'CustomU_'+kind+'_'+ident+'.pdf'}
        checked(rec,kind,True)
        return jsonify(review_token=config.review(packet,rec['token']),pdf_base64=base64.b64encode(raw).decode(),data=packet)
    @app.post('/api/email/send')
    def email_send():
        data=values()
        if set(data)!={'review_token','confirm'} or data['confirm'] is not True:raise failure('EMAIL_CONFIRM_REQUIRED',400)
        rec,_=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not config or not config.ready:raise failure('EMAIL_NOT_CONFIGURED',409)
        packet=valid(config.read_review,data['review_token'],rec['token']);kind=packet['kind'];me=checked(rec,kind,True)
        if packet['sender']!=config.sender or packet['reply_to']!=config.reply_to:raise failure('EMAIL_REVIEW_EXPIRED',409)
        # A repeated browser request returns recorded state, even after the source
        # was archived; it must never initiate a second provider call.
        history=call(rec,{'op':'list','kind':kind,'document_id':packet['document_id']})['data']
        for old in history:
            if old['id']==packet['id']:
                checked(rec,kind,True);return jsonify(data=old,existing=True)
        if not memory_lock.acquire(False):raise failure('EMAIL_PREVIEW_BUSY',429)
        try:r,_,raw=source(rec,kind,packet['document_id'],True)
        finally:memory_lock.release()
        test=bool(config.test_mode or kind=='invoice' and r.get('is_test',False))
        if test!=packet['test_delivery'] or test and packet['recipient']!=config.test_to:raise failure('EMAIL_REVIEW_EXPIRED',409)
        if r['version']!=packet['document_version'] or hashlib.sha256(raw).hexdigest()!=packet['pdf_sha256']:raise failure('EMAIL_DOCUMENT_CHANGED',409)
        claim={k:v for k,v in packet.items() if k not in ('session','expires')};claim.update(op='claim',pdf_base64=base64.b64encode(raw).decode())
        result=call(rec,claim,True,me)
        if result.get('send_now') is not True:checked(rec,kind,True);return jsonify(data=result['data'],existing=True)
        # Read back committed frozen data before calling Resend. An ambiguous DB
        # result stops here. Subsequent requests only display the persisted state.
        row=call(rec,{'op':'get','id':packet['id']})['data']
        if any(row.get(k)!=v for k,v in claim.items() if k!='op') or row.get('state')!='attempted':raise failure('EMAIL_RECORD_UNCERTAIN',503)
        checked(rec,kind,True)
        state,provider_id,code=app.extensions['email_transport'].send(row)
        try:
            final=call(rec,{'op':'settle','id':row['id'],'state':state,'provider_id':provider_id,'error_code':code},True)
            checked(rec,kind,True);return jsonify(data=final['data'],existing=False)
        except failure as exc:
            if exc.status in (401,403):raise
            raise failure('EMAIL_RECORD_UNCERTAIN',503) from None
