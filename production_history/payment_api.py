from staff_access import allowed
"""Administrator-only manual payment records. No money movement or external messaging."""
from flask import request,jsonify
from workspace_codec import parse
from payment_print import render_receipt

def install(app,provider,session,enabled,root,failure):
    def gate(payload=None,admin=False):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if (admin and me.get('role')!='admin') or not allowed(me,'payments',payload):raise failure('ACCESS_DENIED',403)
        return rec
    def rpc(payload):
        rec=gate(payload);r=parse(provider.call('/rest/v1/rpc/custom_u_payments_099',rec['token'],{'payload':payload},limit=2*1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'BALANCE_CHANGED':409,'ID_CONFLICT':409,'ALREADY_REVERSED':409,'FINALISED_INVOICE_REQUIRED':409}.get(r['error'],400))
        me=provider.access(rec['token'])
        if not allowed(me,'payments',payload):raise failure('ACCESS_DENIED',403)
        return r
    @app.get('/payments')
    def payment_page():return app.response_class((root/'static/payments.html').read_bytes(),mimetype='text/html')
    @app.get('/payments.js')
    def payment_script():return app.response_class((root/'static/payments.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/payments')
    def payment_listing():return jsonify(rpc({'op':'list','q':request.args.get('q',''),'page':request.args.get('page','1')}))
    @app.get('/api/payments/invoice/<ident>')
    def payment_invoice(ident):return jsonify(rpc({'op':'invoice','invoice_id':ident}))
    @app.post('/api/payments/save')
    def payment_save():
        gate();request.max_content_length=16384;body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('record','reverse'):raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(body))
    @app.get('/payments/<ident>/print')
    def payment_printable(ident):
        r=rpc({'op':'receipt','id':ident});return app.response_class(render_receipt(r['invoice'],r['payment']),mimetype='text/html')
