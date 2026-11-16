"""Administrator previews and durable, isolated rehearsals. No live import route."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
import uuid
from opening_print import printable
from flask import request, jsonify, make_response
from workspace_codec import parse
from opening_rules import canonical, make_plan, validate_batch, MAX_CSV


def install(app,provider,session,enabled,root,failure):
    plans={}; lock=threading.Lock()
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec,me,hashlib.sha256(rec['token'].encode()).hexdigest()
    def rpc(rec,payload):
        r=parse(provider.call('/rest/v1/rpc/custom_u_opening_110',rec['token'],{'payload':payload},limit=5_000_000))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],403 if r['error']=='ACCESS_DENIED' else 409)
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return r
    def batch(ident):
        rec,_,_=gate();r=rpc(rec,{'op':'get','id':ident}).get('data')
        try:validate_batch(r)
        except (ValueError,TypeError,KeyError):raise failure('OPENING_SAVED_CHECK_FAILED',409) from None
        return r
    @app.get('/opening-balances')
    def opening_page():return app.response_class((root/'static/opening.html').read_bytes(),mimetype='text/html')
    @app.get('/opening.js')
    def opening_script():return app.response_class((root/'static/opening.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/opening')
    def opening_list():
        rec,_,_=gate();return jsonify(rpc(rec,{'op':'list'}))
    @app.get('/api/opening/<ident>')
    def opening_get(ident):return jsonify(data={k:v for k,v in batch(ident).items() if k!='csv_base64'})
    @app.get('/opening-balances/<ident>/print')
    def opening_print(ident):return app.response_class(printable(batch(ident)),mimetype='text/html')
    @app.get('/api/opening/<ident>/source')
    def opening_source(ident):
        r=batch(ident);out=make_response(base64.b64decode(r['csv_base64'],validate=True))
        out.headers['Content-Type']='text/csv; charset=utf-8';out.headers['Content-Disposition']='attachment; filename="ShopVox_Source_'+r['source_sha256'][:12]+'.csv"';return out
    @app.post('/api/opening/preview')
    def opening_preview():
        rec,_,owner=gate();request.max_content_length=2_000_000;body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'csv_base64','as_of','source_name','review','mappings'}:raise failure('INVALID_REQUEST',400)
        state=rpc(rec,{'op':'inspect'})
        try:plan,report=make_plan(body['csv_base64'],body['as_of'],body['source_name'],body['review'],state['customers'],body['mappings'])
        except (ValueError,UnicodeError) as e:
            code=str(e) if re.fullmatch(r'OPENING_[A-Z_]+',str(e)) else 'OPENING_DATA_INVALID'
            raise failure(code,400) from None
        gate();token=secrets.token_urlsafe(32)
        with lock:
            for k in [k for k,v in plans.items() if v['until']<=time.time() or v['owner']==owner]:plans.pop(k)
            if len(plans)>=8:raise failure('OPENING_BUSY',429)
            plans[token]={'owner':owner,'until':time.time()+600,'plan':plan,'can_save':report['can_save'],'id':str(uuid.uuid4()),'running':False,'result':None}
        return jsonify(preview_id=token,expires_in=600,report=report,customers=[r for r in state['customers'] if r['active']])
    @app.post('/api/opening/save')
    def opening_save():
        rec,me,owner=gate();body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'preview_id','confirm_rehearsal'} or body['confirm_rehearsal'] is not True or not isinstance(body['preview_id'],str):raise failure('OPENING_CONFIRM_REQUIRED',400)
        with lock:
            item=plans.get(body['preview_id'])
            if not item or item['owner']!=owner or item['until']<=time.time():raise failure('OPENING_PREVIEW_EXPIRED',409)
            if item['result'] is not None:return jsonify(item['result'])
            if not item['can_save']:raise failure('OPENING_MAPPING_REQUIRED',409)
            if item['running']:raise failure('OPENING_BUSY',429)
            item['running']=True
        try:
            secret=os.getenv('CUSTOMU_EMAIL_SIGNING_SECRET','')
            if not re.fullmatch(r'[a-f0-9]{64}',secret):raise failure('OPENING_SIGNING_SETUP_REQUIRED',409)
            message=canonical({'actor_id':me['user_id'],'expires':int(time.time())+90,'id':item['id'],'plan_json':canonical(item['plan'])})
            signature=hmac.new(bytes.fromhex(secret),('opening110\n'+message).encode(),hashlib.sha256).hexdigest()
            result=rpc(rec,{'op':'signed','message':message,'signature':signature})
            saved=result.get('data',{})
            if saved.get('plan_sha256')!=hashlib.sha256(canonical(item['plan']).encode()).hexdigest() or saved.get('totals')!=item['plan']['totals'] or saved.get('mode')!='rehearsal':raise failure('OPENING_RESULT_UNCONFIRMED')
            with lock:item['result']=result
            return jsonify(result)
        finally:
            with lock:item['running']=False
