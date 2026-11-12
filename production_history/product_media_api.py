"""Private catalogue images and user-reviewed public supplier imports."""
import base64,hashlib,re,threading,time
from flask import request,jsonify,make_response
from staff_access import can
from workspace_codec import parse
from supplier_import import fetch_public,parse_page,public_url,ImportProblem
from product_images import encode_image,checked_bytes,safe_filename,MAX_INPUT

UUID=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def install(app,provider,session,enabled,failure):
    work_lock=threading.Lock();recent={}
    app.extensions['catalogue_memory_lock']=work_lock
    def permission(me,action):
        return can(me,'products.view') and (action=='view' or action=='edit' and can(me,'products.edit') or action=='import' and (can(me,'products.create') or can(me,'products.edit')))
    def gate(action='view'):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not permission(me,action):raise failure('ACCESS_DENIED',403)
        return rec
    def check(rec,action='view'):
        if not permission(provider.access(rec['token']),action):raise failure('ACCESS_DENIED',403)
    def ident(value):
        if not isinstance(value,str) or not UUID.fullmatch(value):raise failure('INVALID_ID',400)
    def rpc(rec,payload,action='view'):
        result=parse(provider.call('/rest/v1/rpc/custom_u_product_images_106',rec['token'],{'payload':payload},limit=2_000_000))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'IMAGE_ID_CONFLICT':409}.get(result['error'],400))
        check(rec,action);return result
    def body(keys,limit=8192):
        request.max_content_length=limit
        value=request.get_json()
        if not isinstance(value,dict) or set(value)!=set(keys):raise failure('INVALID_REQUEST',400)
        return value
    def begin(rec,throttle=False):
        if not work_lock.acquire(blocking=False):raise failure('PRODUCT_IMAGE_BUSY',429)
        if throttle:
            now=time.monotonic();key=hashlib.sha256(rec['token'].encode()).hexdigest()
            for old in [k for k,t in recent.items() if now-t>60]:recent.pop(old)
            if now-recent.get(key,-100)<2:
                work_lock.release();raise failure('PLEASE_WAIT_AND_TRY_AGAIN',429)
            recent[key]=now
    @app.post('/api/products/import-preview')
    def import_preview():
        rec=gate('import');value=body({'url'});begin(rec,True)
        try:
            raw,url,_=fetch_public(value['url']);result=parse_page(raw,url);check(rec,'import');return jsonify(result)
        except ImportProblem as e:raise failure(str(e),400) from None
        finally:work_lock.release()
    @app.post('/api/products/import-image')
    def import_image():
        rec=gate('import');value=body({'url'});begin(rec,True)
        try:
            raw,url,_=fetch_public(value['url'],image=True)
            try:result=encode_image(raw)
            except ValueError as e:raise failure(str(e),400) from None
            check(rec,'import');return jsonify({**result,'source_url':url,'filename':'supplier-image.webp'})
        except ImportProblem as e:raise failure(str(e),400) from None
        finally:work_lock.release()
    @app.get('/api/products/<product>/images')
    def image_list(product):
        ident(product);rec=gate();return jsonify(rpc(rec,{'op':'list','product_id':product}))
    @app.get('/api/products/<product>/images/<image>')
    def image_get(product,image):
        ident(product);ident(image);rec=gate();record=rpc(rec,{'op':'get','product_id':product,'id':image})['data']
        try:raw=checked_bytes(record)
        except ValueError:raise failure('IMAGE_INTEGRITY_FAILED',409) from None
        check(rec);response=make_response(raw);response.headers['Content-Type']='image/webp'
        response.headers['Content-Disposition']=('attachment' if request.args.get('download')=='1' else 'inline')+'; filename="'+safe_filename(record.get('filename','image.webp'))+'"'
        return response
    @app.post('/api/products/<product>/images/add')
    def image_add(product):
        ident(product);rec=gate('edit');value=body({'id','filename','caption','source_url','data'},16_100_000);ident(value['id'])
        if not isinstance(value['data'],str) or len(value['data'])>16_000_000 or not isinstance(value['filename'],str) or len(value['filename'])>255 or not isinstance(value['caption'],str) or len(value['caption'])>200 or re.search(r'[\x00-\x1f\x7f]',value['caption']):raise failure('INVALID_IMAGE',400)
        try:source_url=public_url(value['source_url']) if value['source_url'] else ''
        except ImportProblem:raise failure('SUPPLIER_URL_INVALID',400) from None
        if not isinstance(value['source_url'],str):raise failure('SUPPLIER_URL_INVALID',400)
        try:raw=base64.b64decode(value['data'],validate=True)
        except (ValueError,TypeError):raise failure('INVALID_IMAGE',400) from None
        begin(rec)
        try:
            try:prepared=encode_image(raw)
            except ValueError as e:raise failure(str(e),400) from None
            check(rec,'edit')
            result=rpc(rec,{'op':'add','product_id':product,'id':value['id'],'filename':safe_filename(value['filename']),'caption':value['caption'].strip(),'source_url':source_url,**{k:v for k,v in prepared.items() if k!='size_bytes'}},'edit')
            saved=rpc(rec,{'op':'get','product_id':product,'id':value['id']},'edit')['data']
            try:actual=checked_bytes(saved)
            except ValueError:raise failure('IMAGE_INTEGRITY_FAILED',409) from None
            if hashlib.sha256(actual).hexdigest()!=prepared['sha256']:raise failure('IMAGE_INTEGRITY_FAILED',409)
            check(rec,'edit');return jsonify(result)
        finally:work_lock.release()
    @app.post('/api/products/<product>/images/<image>/active')
    def image_active(product,image):
        ident(product);ident(image);rec=gate('edit');value=body({'version','active'})
        if type(value['version']) is not int or type(value['active']) is not bool:raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(rec,{'op':'set_active','product_id':product,'id':image,**value},'edit'))
