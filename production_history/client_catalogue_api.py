"""Authenticated client catalogue preview, snapshots and private PDF download."""
from flask import request,jsonify,make_response
from staff_access import can
from workspace_codec import parse
from catalogue_data import uid,text,items_valid
from catalogue_pdf import render_catalogue


def install(app,provider,session,enabled,root,failure):
    lock=app.extensions['catalogue_memory_lock']
    def allowed(me,write=False):return can(me,'products.view') and can(me,'customers.view') and (not write or can(me,'products.edit'))
    def gate(write=False):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not allowed(me,write):raise failure('ACCESS_DENIED',403)
        return rec
    def check(rec,write=False):
        if not allowed(provider.access(rec['token']),write):raise failure('ACCESS_DENIED',403)
    def rpc(rec,payload,write=False,missing=False):
        result=parse(provider.call('/rest/v1/rpc/custom_u_client_catalogues_108',rec['token'],{'payload':payload},limit=9_000_000))
        check(rec,write)
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if missing and result.get('error')=='NOT_FOUND':return None
        if 'error' in result:raise failure(result['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'CATALOGUE_ID_CONFLICT':409,'CATALOGUE_SOURCE_UNAVAILABLE':409}.get(result['error'],400))
        return result
    def body(save=False):
        request.max_content_length=40000;v=request.get_json()
        try:
            if not isinstance(v,dict) or set(v)!=({'id','customer_id','title','intro','items'} if save else {'customer_id','title','intro','items'}):raise ValueError()
            if save:uid(v['id'])
            uid(v['customer_id']);text(v['title'],120,True);text(v['intro'],600);items_valid(v['items'])
        except (ValueError,TypeError):raise failure('INVALID_CATALOGUE',400) from None
        return v
    def pdf(result):
        try:return render_catalogue(result['data'],result['assets'])
        except (ValueError,KeyError,TypeError):raise failure('CATALOGUE_RENDER_FAILED',409) from None
    def response(raw,ident='preview',download=False):
        out=make_response(raw);out.headers['Content-Type']='application/pdf';out.headers['Content-Disposition']=('attachment' if download else 'inline')+'; filename="CustomU_Client_Catalogue_'+ident+'.pdf"';return out
    @app.get('/catalogues')
    def catalogue_page():return app.response_class((root/'static/catalogues.html').read_bytes(),mimetype='text/html')
    @app.get('/catalogues.js')
    def catalogue_script():return app.response_class((root/'static/catalogues.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/catalogues')
    def catalogue_list():
        rec=gate();return jsonify(rpc(rec,{'op':'list','q':request.args.get('q',''),'state':request.args.get('state','active'),'page':request.args.get('page','1')}))
    @app.get('/api/catalogues/options')
    def catalogue_options():
        rec=gate(True);return jsonify(rpc(rec,{'op':'options','product_id':request.args.get('product_id',''),'customer_id':request.args.get('customer_id','')} ,True))
    @app.post('/api/catalogues/preview')
    def catalogue_preview():
        rec=gate(True);v=body()
        if not lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        try:
            raw=pdf(rpc(rec,{'op':'prepare',**v},True));check(rec,True);return response(raw)
        finally:lock.release()
    @app.post('/api/catalogues/save')
    def catalogue_save():
        rec=gate(True);v=body(True)
        if not lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        try:
            prior=rpc(rec,{'op':'get','id':v['id']},True,missing=True)
            if prior is None:pdf(rpc(rec,{'op':'prepare',**{k:val for k,val in v.items() if k!='id'}},True))
            result=rpc(rec,{'op':'save',**v},True)
            saved=rpc(rec,{'op':'get','id':v['id']},True)['data']
            if any(saved.get(k)!=val for k,val in v.items()):raise failure('CATALOGUE_VERIFY_FAILED',409)
            check(rec,True);return jsonify(result)
        finally:lock.release()
    @app.get('/api/catalogues/<ident>')
    def catalogue_detail(ident):
        rec=gate();return jsonify(rpc(rec,{'op':'get','id':ident}))
    @app.get('/api/catalogues/<ident>/pdf')
    def catalogue_download(ident):
        rec=gate()
        try:uid(ident)
        except ValueError:raise failure('INVALID_REQUEST',400) from None
        if not lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        try:
            raw=pdf(rpc(rec,{'op':'document','id':ident}));check(rec);return response(raw,ident,request.args.get('download')=='1')
        finally:lock.release()
    @app.post('/api/catalogues/<ident>/active')
    def catalogue_status(ident):
        rec=gate(True);request.max_content_length=8192;v=request.get_json()
        if not isinstance(v,dict) or set(v)!={'active','version'} or type(v['active']) is not bool or type(v['version']) is not int:raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(rec,{'op':'set_active','id':ident,**v},True))
