"""Private customer-linked mockup drafts and immutable saved previews."""
import base64,hashlib,re
from flask import request,jsonify,make_response
from staff_access import can
from workspace_codec import parse
from product_images import encode_image,checked_bytes
from mockup_render import configuration,render

UUID=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
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
    def ident(v):
        if not isinstance(v,str) or not UUID.fullmatch(v):raise failure('INVALID_ID',400)
    def rpc(rec,payload,write=False):
        r=parse(provider.call('/rest/v1/rpc/custom_u_mockups_107',rec['token'],{'payload':payload},limit=2_000_000))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'MOCKUP_ID_CONFLICT':409}.get(r['error'],400))
        check(rec,write);return r
    def body(keys,limit=16_100_000):
        request.max_content_length=limit;v=request.get_json()
        if not isinstance(v,dict) or set(v)!=set(keys):raise failure('INVALID_REQUEST',400)
        return v
    @app.get('/mockups')
    def mockup_page():return app.response_class((root/'static/mockups.html').read_bytes(),mimetype='text/html')
    @app.get('/mockups.js')
    def mockup_script():return app.response_class((root/'static/mockups.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/mockups')
    def mockup_listing():
        rec=gate();return jsonify(rpc(rec,{'op':'list','q':request.args.get('q',''),'page':request.args.get('page','1'),'state':request.args.get('state','active')}))
    @app.post('/api/mockups/preview')
    def mockup_preview():
        rec=gate(True);v=body({'product_id','image_id','logo','config'})
        ident(v['product_id']);ident(v['image_id'])
        if not isinstance(v['logo'],str) or len(v['logo'])>16_000_000:raise failure('INVALID_IMAGE',400)
        if not lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        try:
            try:raw=base64.b64decode(v['logo'],validate=True);config=configuration(v['config']);logo=encode_image(raw)
            except (ValueError,TypeError):raise failure('INVALID_MOCKUP',400) from None
            image=rpc(rec,{'op':'source','product_id':v['product_id'],'image_id':v['image_id']},True)['data']
            try:result=render(image,logo,config)
            except ValueError as e:raise failure(str(e),400) from None
            check(rec,True);return jsonify({'preview':result,'logo':logo,'config':config,'source_sha256':image['sha256']})
        finally:lock.release()
    @app.post('/api/mockups/save')
    def mockup_save():
        rec=gate(True);v=body({'id','product_id','image_id','customer_id','title','logo','config','source_sha256'},1_000_000)
        for k in ('id','product_id','image_id','customer_id'):ident(v[k])
        if not isinstance(v['title'],str) or not 1<=len(v['title'].strip())<=160 or re.search(r'[\x00-\x1f\x7f]',v['title']):raise failure('INVALID_MOCKUP',400)
        if not lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        try:
            try:configuration(v['config']);checked_bytes(v['logo'])
            except (ValueError,TypeError):raise failure('INVALID_MOCKUP',400) from None
            image=rpc(rec,{'op':'source','product_id':v['product_id'],'image_id':v['image_id']},True)['data']
            if image['sha256']!=v['source_sha256']:raise failure('VERSION_CONFLICT',409)
            try:composite=render(image,v['logo'],v['config'])
            except ValueError as e:raise failure(str(e),400) from None
            payload={k:val for k,val in v.items() if k!='source_sha256'};payload.update(op='add',title=v['title'].strip(),preview=composite)
            result=rpc(rec,payload,True)
            saved=rpc(rec,{'op':'get','id':v['id']},True)['data']
            try:
                if checked_bytes(saved['preview'])!=checked_bytes(composite) or checked_bytes(saved['logo'])!=checked_bytes(v['logo']):raise ValueError()
            except ValueError:raise failure('IMAGE_INTEGRITY_FAILED',409) from None
            return jsonify(result)
        finally:lock.release()
    @app.get('/api/mockups/<mid>')
    def mockup_detail(mid):
        ident(mid);rec=gate();return jsonify(rpc(rec,{'op':'get','id':mid}))
    @app.get('/api/mockups/<mid>/image')
    def mockup_image(mid):
        ident(mid);rec=gate();r=rpc(rec,{'op':'get','id':mid})['data']
        try:raw=checked_bytes(r['preview'])
        except ValueError:raise failure('IMAGE_INTEGRITY_FAILED',409) from None
        check(rec);response=make_response(raw);response.headers['Content-Type']='image/webp'
        response.headers['Content-Disposition']=('attachment' if request.args.get('download')=='1' else 'inline')+'; filename="CustomU_Mockup_'+mid+'.webp"';return response
    @app.post('/api/mockups/<mid>/active')
    def mockup_active(mid):
        ident(mid);rec=gate(True);v=body({'version','active'},8192)
        if type(v['version']) is not int or type(v['active']) is not bool:raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(rec,{'op':'set_active','id':mid,**v},True))
