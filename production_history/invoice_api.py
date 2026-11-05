"""Private invoice routes; saving and finalising are distinct explicit operations."""
from flask import request,jsonify
from workspace_codec import parse
from invoice_print import render_invoice
from document_terms import INVOICE_TERMS

def install(app,provider,session,enabled,root,failure):
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec
    def rpc(payload):
        rec=gate();r=parse(provider.call('/rest/v1/rpc/custom_u_invoices_098',rec['token'],{'payload':payload},limit=1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'QUOTE_NOT_FOUND':404,'INVOICE_LOCKED':409,'VERSION_CONFLICT':409,'ID_CONFLICT':409,'FINALISED_QUOTE_REQUIRED':409}.get(r['error'],400))
        provider.access(rec['token']);return r
    @app.get('/invoices')
    def invoice_page():return app.response_class((root/'static/invoices.html').read_bytes(),mimetype='text/html')
    @app.get('/invoices.js')
    def invoice_script():return app.response_class((root/'static/invoices.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/invoices')
    def invoice_listing():return jsonify(rpc({'op':'list','q':request.args.get('q',''),'page':request.args.get('page','1')}))
    @app.get('/api/invoices/defaults')
    def invoice_defaults():gate();return jsonify(terms=INVOICE_TERMS)
    @app.get('/api/invoices/<ident>')
    def invoice_detail(ident):return jsonify(rpc({'op':'get','id':ident}))
    @app.post('/api/invoices/save')
    def invoice_save():
        gate();request.max_content_length=32768;body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('create','save','issue'):raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(body))
    @app.get('/invoices/<ident>/print')
    def invoice_printable(ident):return app.response_class(render_invoice(rpc({'op':'get','id':ident})['data']),mimetype='text/html')
