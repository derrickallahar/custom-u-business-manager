"""Administrator customer/contact routes. All durable writes use the 093 RPC."""
import json
from flask import request, jsonify


def install(app, provider, session, enabled, root, failure):
    def gate():
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if me.get('role') != 'admin':
            raise failure('ACCESS_DENIED', 403)
        return rec

    def rpc(payload):
        rec = gate()
        result = json.loads(provider.call('/rest/v1/rpc/custom_u_crm_093',
                            rec['token'], {'payload': payload}, limit=1000000))
        if not isinstance(result, dict):
            raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            status = {'ACCESS_DENIED': 403, 'NOT_FOUND': 404,
                      'VERSION_CONFLICT': 409, 'ID_CONFLICT': 409,
                      'CUSTOMER_INACTIVE': 409}.get(result['error'], 400)
            raise failure(result['error'], status)
        return jsonify(result)

    @app.get('/customers')
    def page():
        # Static shell contains no private records. API access requires live auth.
        return app.response_class((root/'static/customers.html').read_bytes(), mimetype='text/html')

    @app.get('/customers.js')
    def crm_javascript():
        return app.response_class((root/'static/customers.js').read_bytes(), mimetype='text/javascript')

    @app.get('/api/customers')
    def crm_listing():
        return rpc({'op': 'list', 'q': request.args.get('q', ''),
                    'page': request.args.get('page', '1')})

    @app.get('/api/customers/<ident>')
    def crm_detail(ident):
        return rpc({'op': 'get', 'id': ident})

    @app.post('/api/customers/save')
    def save():
        body = request.get_json()
        if not isinstance(body, dict) or body.get('op') not in ('save_customer', 'save_contact'):
            raise failure('INVALID_REQUEST', 400)
        return rpc(body)
