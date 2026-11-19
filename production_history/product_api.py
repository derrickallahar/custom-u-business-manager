"""Authenticated reusable products. Existing quote lines copy values independently."""
from flask import request, jsonify
from staff_access import can
from workspace_codec import parse
from area_pricing import calculate as calculate_area, selected_product as selected_area_product


def install(app, provider, session, enabled, root, failure):
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

    @app.get('/products.js')
    def product_script():
        return app.response_class((root/'static/products.js').read_bytes(), mimetype='text/javascript')

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

    @app.get('/api/products')
    def product_list():
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
