"""Authenticated quotes, printable saved documents, and combined workspace backup."""
import hashlib,json,threading,time
from datetime import datetime,timezone
from flask import request,jsonify,make_response
from quote_print import render_quote
from document_terms import QUOTE_TERMS
from workspace_codec import encrypt,parse,passphrase_bytes,MAX_BYTES


def install(app,provider,session,enabled,root,failure):
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec

    def rpc(payload):
        rec=gate()
        result=parse(provider.call('/rest/v1/rpc/custom_u_quotes_097',rec['token'],{'payload':payload},limit=1024*1024))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            code=result['error'];raise failure(code,{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'QUOTE_LOCKED':409,'BUSINESS_PROFILE_REQUIRED':409,'CUSTOMER_INACTIVE':409}.get(code,400))
        provider.access(rec['token'])
        return result

    @app.get('/quotes')
    def quote_page():return app.response_class((root/'static/quotes.html').read_bytes(),mimetype='text/html')
    @app.get('/quotes.js')
    def quote_script():return app.response_class((root/'static/quotes.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/quotes')
    def quote_list():return jsonify(rpc({'op':'list','q':request.args.get('q',''),'page':request.args.get('page','1')}))
    @app.get('/api/quotes/profile')
    def profile():
        result=rpc({'op':'profile'});result['default_terms']=QUOTE_TERMS;return jsonify(result)
    @app.get('/api/quotes/<ident>')
    def quote_detail(ident):return jsonify(rpc({'op':'get','id':ident}))
    @app.post('/api/quotes/save')
    def quote_save():
        gate();request.max_content_length=262144
        body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('save','issue','save_profile'):raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(body))
    @app.get('/quotes/<ident>/print')
    def quote_print(ident):
        result=rpc({'op':'get','id':ident})
        return app.response_class(render_quote(result['data']),mimetype='text/html')

    lock=threading.Lock();last={}
    @app.post('/api/quotes/backup')
    def workspace_backup():
        rec=gate();body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'passphrase'}:raise failure('INVALID_REQUEST',400)
        password=body['passphrase']
        try:passphrase_bytes(password)
        except ValueError:raise failure('PASSPHRASE_LENGTH',400) from None
        if not lock.acquire(blocking=False):raise failure('BACKUP_BUSY',429)
        try:
            now=time.monotonic();owner=hashlib.sha256(rec['token'].encode()).hexdigest()
            if now-last.get(owner,-100)<30:raise failure('BACKUP_WAIT_30_SECONDS',429)
            last.clear();last[owner]=now
            raw=provider.call('/rest/v1/rpc/custom_u_workspace_snapshot_100',rec['token'],{},limit=MAX_BYTES)
            obj=parse(raw)
            if not isinstance(obj,dict):raise failure('INVALID_BACKUP_RESPONSE')
            if 'error' in obj:raise failure(obj['error'],403 if obj['error']=='ACCESS_DENIED' else 503)
            if obj.get('format')!='custom-u-workspace-snapshot-100' or not isinstance(obj.get('crm'),dict) or 'error' in obj['crm'] or not isinstance(obj.get('quotes'),list) or not isinstance(obj.get('audit'),list) or not isinstance(obj.get('invoices'),list) or not isinstance(obj.get('invoice_audit'),list) or not isinstance(obj.get('payments'),list) or not isinstance(obj.get('payment_audit'),list) or not isinstance(obj.get('credits'),list) or not isinstance(obj.get('refunds'),list) or not isinstance(obj.get('adjustment_audit'),list):raise failure('INVALID_BACKUP_RESPONSE')
            provider.access(rec['token']);blob=encrypt(raw,password)
            name='CustomU_Workspace_100_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+hashlib.sha256(blob).hexdigest()[:8]+'.cuwork'
            response=make_response(blob);response.headers['Content-Type']='application/octet-stream';response.headers['Content-Disposition']='attachment; filename="'+name+'"';return response
        finally:
            password=None;body=None;lock.release()
