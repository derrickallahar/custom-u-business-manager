"""Administrator-only credit notes and recording of refunds already made."""
from flask import request,jsonify
from workspace_codec import parse
from adjustment_print import render_credit,render_refund

def install(app,provider,session,enabled,root,failure):
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec
    def rpc(payload):
        rec=gate();r=parse(provider.call('/rest/v1/rpc/custom_u_adjustments_100',rec['token'],{'payload':payload},limit=8*1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'BALANCE_CHANGED':409,'VERSION_CONFLICT':409,'ID_CONFLICT':409,'CREDIT_LOCKED':409,'CREDIT_CHANGED':409,'ALREADY_REVERSED':409,'FINALISED_INVOICE_REQUIRED':409}.get(r['error'],400))
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return r
    @app.get('/credits')
    def adjustment_page():return app.response_class((root/'static/credits.html').read_bytes(),mimetype='text/html')
    @app.get('/credits.js')
    def adjustment_script():return app.response_class((root/'static/credits.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/credits/invoice/<ident>')
    def adjustment_invoice(ident):return jsonify(rpc({'op':'invoice','invoice_id':ident}))
    @app.post('/api/credits/save')
    def adjustment_save():
        gate();request.max_content_length=32768;body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('save_credit','issue_credit','record_refund','reverse_refund'):raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(body))
    @app.get('/credits/<ident>/print')
    def credit_printable(ident):
        r=rpc({'op':'credit','id':ident});return app.response_class(render_credit(r['invoice'],r['credit']),mimetype='text/html')
    @app.get('/refunds/<ident>/print')
    def refund_printable(ident):
        r=rpc({'op':'refund','id':ident});return app.response_class(render_refund(r['invoice'],r['refund']),mimetype='text/html')
