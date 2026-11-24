"""Authenticated reusable products. Existing quote lines copy values independently."""
from flask import request, jsonify
from staff_access import can
from workspace_codec import parse
from catalogue_pricing import calculate as calculate_catalogue
import json
import re
import hashlib
from area_pricing import calculate as calculate_area, selected_product as selected_area_product


def install(app, provider, session, enabled, root, failure):
    from bulk_pricing_api import install as install_bulk
    install_bulk(app,provider,session,enabled,root,failure)
    from product_csv_api import install as install_csv
    install_csv(app, provider, session, enabled, root, failure)

    def permitted(me, payload):
        key = 'products.view'
        if payload.get('op') == 'save':
            key = 'products.create' if payload.get('version') == 0 else 'products.edit'
        return can(me, 'products.view') and can(me, key)

    def gate(payload):
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if not permitted(me, payload):
            raise failure('ACCESS_DENIED', 403)
        return rec

    def rpc(payload):
        rec = gate(payload)
        # Legacy five-field saves remain compatible and cannot erase supplier data.
        version = '105' if payload.get('op') == 'save' and 'supplier' not in payload else '106'
        result = parse(provider.call('/rest/v1/rpc/custom_u_products_'+version, rec['token'], {'payload': payload}, limit=2*1024*1024))
        if not isinstance(result, dict):
            raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            code = result['error']
            raise failure(code, {'ACCESS_DENIED': 403, 'NOT_FOUND': 404, 'VERSION_CONFLICT': 409, 'PRODUCT_CODE_EXISTS': 409}.get(code, 400))
        if not permitted(provider.access(rec['token']), payload):
            raise failure('ACCESS_DENIED', 403)
        return result

    @app.get('/products')
    def product_page():
        return app.response_class((root/'static/products.html').read_bytes(), mimetype='text/html')

    @app.get('/products/new')
    @app.get('/products/<uuid:ident>')
    def product_detail_page(ident=None):
        return app.response_class((root/'static/products.html').read_bytes(), mimetype='text/html')

    @app.get('/products.js')
    def product_script():
        return app.response_class((root/'static/products.js').read_bytes(), mimetype='text/javascript')

    @app.get('/pricing-picker.js')
    def pricing_picker_script():
        return app.response_class((root/'static/pricing-picker.js').read_bytes(), mimetype='text/javascript')

    def starter_gate():
        # One current access read, followed by the RPC's own authorization and a
        # post-write recheck. Avoid the former duplicate session/access request.
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if me.get('role') != 'admin' or not permitted(me, {'op': 'save', 'version': 0}):
            raise failure('ACCESS_DENIED', 403)
        return rec

    def starter_source():
        raw = (root/'catalogue_starters.json').read_bytes()
        items = json.loads(raw)
        if not isinstance(items, list) or not 1 <= len(items) <= 250:
            raise failure('STARTER_SOURCE_INVALID', 503)
        return items, hashlib.sha256(raw).hexdigest()

    @app.post('/api/products/setup-starters')
    def setup_starters():
        # A page left open from 114.6 must reload rather than silently process
        # only part of the old all-at-once request.
        starter_gate()
        raise failure('STARTER_SETUP_RELOAD_REQUIRED', 409)

    @app.get('/api/products/setup-starters/plan')
    def starter_plan():
        starter_gate()
        items, digest = starter_source()
        return jsonify(source_sha256=digest, total=len(items), batch_size=10)

    @app.post('/api/products/setup-starters/batch')
    def starter_batch():
        rec = starter_gate()
        body = request.get_json()
        if (not isinstance(body, dict) or set(body) != {'add_unpriced_starters', 'source_sha256', 'offset'}
                or body['add_unpriced_starters'] is not True or type(body['offset']) is not int
                or not isinstance(body['source_sha256'], str)):
            raise failure('INVALID_REQUEST', 400)
        items, digest = starter_source()
        if body['source_sha256'] != digest:
            raise failure('STARTER_SOURCE_CHANGED', 409)
        offset = body['offset']
        if not 0 <= offset < len(items) or offset % 10:
            raise failure('INVALID_REQUEST', 400)
        chunk = items[offset:offset+10]
        result = parse(provider.call('/rest/v1/rpc/custom_u_catalogue_setup_1146', rec['token'], {'payload': {'items': chunk}}, limit=100000))
        me = provider.access(rec['token'])
        if me.get('role') != 'admin' or not permitted(me, {'op': 'save', 'version': 0}):
            raise failure('ACCESS_DENIED', 403)
        if isinstance(result, dict) and result.get('error') == 'ACCESS_DENIED':
            raise failure('ACCESS_DENIED', 403)
        if (not isinstance(result, dict) or 'error' in result
                or type(result.get('added')) is not int or type(result.get('existing')) is not int
                or min(result['added'], result['existing']) < 0
                or result['added']+result['existing'] != len(chunk)):
            raise failure('STARTER_SETUP_UNCONFIRMED', 503)
        return jsonify(source_sha256=digest, total=len(items), offset=offset,
                       next_offset=offset+len(chunk), added=result['added'], existing=result['existing'])

    @app.post('/api/products/configured-price')
    def configured_price():
        gate({'op': 'get'})
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get('product_id'), str) or not re.fullmatch(r'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}', body['product_id']):
            raise failure('INVALID_PRICING_REQUEST', 400)
        result = rpc({'op': 'get', 'id': body['product_id']})
        try:
            return jsonify(calculate_catalogue(body, result.get('data')))
        except ValueError as error:
            raise failure(str(error), 400) from None

    @app.get('/brochure-picker.js')
    def brochure_picker_script():
        return app.response_class((root/'static/brochure-picker.js').read_bytes(), mimetype='text/javascript')

    @app.get('/flyer-picker.js')
    def flyer_picker_script():
        return app.response_class((root/'static/flyer-picker.js').read_bytes(), mimetype='text/javascript')

    @app.get('/area-picker.js')
    def area_picker_script():
        return app.response_class((root/'static/area-picker.js').read_bytes(), mimetype='text/javascript')

    @app.post('/api/products/area-price')
    def area_price():
        # Uses the same authenticated, rechecked product-view permission as reads.
        # Only the current saved product rate is accepted; client rates are not inputs.
        gate({'op': 'get'})
        body = request.get_json()
        try:
            ident = selected_area_product(body)
        except ValueError as error:
            raise failure(str(error), 400) from None
        result = rpc({'op': 'get', 'id': ident})
        try:
            answer = calculate_area(body, result.get('data'))
        except ValueError as error:
            raise failure(str(error), 400) from None
        return jsonify(answer)

    def grouped_rpc(payload):
        rec=gate({'op':'get'})
        result=parse(provider.call('/rest/v1/rpc/custom_u_product_groups_117',rec['token'],{'payload':payload},limit=2*1024*1024))
        if not permitted(provider.access(rec['token']),{'op':'get'}):raise failure('ACCESS_DENIED',403)
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 400)
        return result

    @app.get('/products/options/<family>')
    def product_group_page(family):
        if family not in ('flyers','brochures'):raise failure('NOT_FOUND',404)
        return app.response_class((root/'static/product-group.html').read_bytes(),mimetype='text/html')

    @app.get('/product-group.js')
    def product_group_script():return app.response_class((root/'static/product-group.js').read_bytes(),mimetype='text/javascript')

    @app.get('/api/product-options/<family>')
    def product_group_options(family):
        if family not in ('flyers','brochures'):raise failure('NOT_FOUND',404)
        return jsonify(grouped_rpc({'op':'get','group':family,'state':request.args.get('state','all')}))

    @app.get('/api/products')
    def product_list():
        if request.args.get('grouped')=='1':
            return jsonify(grouped_rpc({'op':'list','q':request.args.get('q',''),'state':request.args.get('state','active'),'page':request.args.get('page','1')}))
        return jsonify(rpc({'op': 'list', 'q': request.args.get('q', ''), 'page': request.args.get('page', '1'), 'state': request.args.get('state', 'active')}))

    @app.get('/api/products/<ident>')
    def product_detail(ident):
        return jsonify(rpc({'op': 'get', 'id': ident}))

    @app.post('/api/products/save')
    def product_save():
        request.max_content_length = 65536
        body = request.get_json()
        if not isinstance(body, dict) or set(body) not in ({'op', 'id', 'version', 'active', 'data'}, {'op', 'id', 'version', 'active', 'data','supplier','supplier_version'}) or body['op'] != 'save' or type(body['version']) is not int or type(body['active']) is not bool or 'supplier_version' in body and type(body['supplier_version']) is not int:
            raise failure('INVALID_REQUEST', 400)
        return jsonify(rpc(body))
