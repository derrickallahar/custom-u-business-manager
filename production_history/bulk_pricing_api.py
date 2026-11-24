"""Reviewed ShopVox pricing batch. Versioned, admin-only, one product per write."""
import hashlib
import copy
import json
import re
from flask import jsonify, request
from pricing_rules import pricing_valid


def plan(source, records):
    normalized=lambda s: re.sub(r'\s+',' ',s.strip().casefold())
    result=[]
    for index, item in enumerate(source):
        matches=[r for r in records if normalized(r['data']['name'])==normalized(item['name'])]
        existing=matches[0] if len(matches)==1 else None
        data=dict(existing['data']) if existing else dict(item['data'])
        for key in ('unit','unit_price','vat_rate','pricing'):data[key]=copy.deepcopy(item['data'][key])
        data['pricing']=dict(data['pricing'])
        if existing and existing['data'].get('pricing',{}).get('minimum'):data['pricing']['minimum']=existing['data']['pricing']['minimum']
        ident=existing['id'] if existing else item['id']
        version=existing['version'] if existing else 0
        state='ready'
        if len(matches)>1 or any(r['id']==ident and normalized(r['data']['name'])!=normalized(item['name']) for r in records):state='conflict'
        elif existing and existing['active'] and existing['data']==data:state='applied'
        elif existing and (existing['active'] or existing['data'].get('unit_price') or existing['data'].get('pricing',{}).get('options')):state='protected'
        if not pricing_valid(data,True):state='invalid'
        result.append({'index':index,'id':ident,'version':version,'name':item['name'],'state':state,'data':data,'sources':item['sources']})
    return result


def install(app,provider,session,enabled,root,failure):
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec
    def source():
        raw=(root/'bulk_prices_120.json').read_bytes()
        items=json.loads(raw)
        if not isinstance(items,list) or not 1<=len(items)<=250 or not all(pricing_valid(x['data'],True) for x in items):raise failure('BULK_SOURCE_INVALID',503)
        return items,hashlib.sha256(raw).hexdigest()
    def rpc(rec,payload):
        result=json.loads(provider.call('/rest/v1/rpc/custom_u_bulk_prices_120',rec['token'],{'payload':payload},limit=8*1024*1024))
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE',503)
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 409)
        return result
    @app.get('/products/bulk-pricing')
    def bulk_page():return app.response_class((root/'static/bulk-pricing.html').read_bytes(),mimetype='text/html')
    @app.get('/bulk-pricing.js')
    def bulk_script():return app.response_class((root/'static/bulk-pricing.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/products/bulk-pricing/preview')
    def bulk_preview():
        rec=gate();items,digest=source();state=rpc(rec,{'op':'inspect'})
        if not isinstance(state.get('records'),list):raise failure('INVALID_PROVIDER_RESPONSE',503)
        return jsonify(source_sha256=digest,rows=plan(items,state['records']))
    @app.post('/api/products/bulk-pricing/apply')
    def bulk_apply():
        rec=gate();body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'index','id','version','source_sha256','confirm'} or body['confirm'] is not True or type(body['index']) is not int or type(body['version']) is not int or not isinstance(body['id'],str) or not isinstance(body['source_sha256'],str):raise failure('INVALID_REQUEST',400)
        items,digest=source()
        if body['source_sha256']!=digest:raise failure('BULK_SOURCE_CHANGED',409)
        if not 0<=body['index']<len(items):raise failure('INVALID_REQUEST',400)
        state=rpc(rec,{'op':'inspect'});row=plan(items,state['records'])[body['index']]
        if row['id']!=body['id']:raise failure('VERSION_CONFLICT',409)
        if row['state']=='applied':return jsonify(index=row['index'],id=row['id'],state='applied',version=row['version'])
        if row['state']!='ready':raise failure('EXISTING_PRICE_PROTECTED',409)
        if row['version']!=body['version']:raise failure('VERSION_CONFLICT',409)
        saved=rpc(rec,{'op':'save','id':row['id'],'version':row['version'],'active':True,'data':row['data']}).get('data')
        if not isinstance(saved,dict) or saved.get('id')!=row['id'] or saved.get('data')!=row['data'] or saved.get('active') is not True or saved.get('version')!=row['version']+1:raise failure('BULK_SAVE_UNCONFIRMED',503)
        return jsonify(index=row['index'],id=row['id'],state='applied',version=saved['version'])
