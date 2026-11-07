"""Authenticated reusable products. Existing quote lines copy values independently."""
from flask import request, jsonify
from staff_access import can
from workspace_codec import parse


def install(app, provider, session, enabled, root, failure):
    def permitted(me, payload):
        key = 'products.view'
        if payload.get('op') == 'save':
            key = 'products.create' if payload.get('version') == 0 else 'products.edit'
        return can(me, 'products.view') and can(me, key)

    def rpc(payload):
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if not permitted(me, payload):
            raise failure('ACCESS_DENIED', 403)
        result = parse(provider.call('/rest/v1/rpc/custom_u_products_105', rec['token'], {'payload': payload}, limit=1024*1024))
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

    @app.get('/products.js')
    def product_script():
        return app.response_class((root/'static/products.js').read_bytes(), mimetype='text/javascript')

    @app.get('/api/products')
    def product_list():
        return jsonify(rpc({'op': 'list', 'q': request.args.get('q', ''), 'page': request.args.get('page', '1'), 'state': request.args.get('state', 'active')}))

    @app.get('/api/products/<ident>')
    def product_detail(ident):
        return jsonify(rpc({'op': 'get', 'id': ident}))

    @app.post('/api/products/save')
    def product_save():
        request.max_content_length = 16384
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {'op', 'id', 'version', 'active', 'data'} or body['op'] != 'save' or type(body['version']) is not int or type(body['active']) is not bool:
            raise failure('INVALID_REQUEST', 400)
        return jsonify(rpc(body))
