from staff_access import allowed
"""Private invoice routes; saving and finalising are distinct explicit operations."""
from flask import request,jsonify
from workspace_codec import parse
from invoice_print import render_invoice
from document_terms import INVOICE_TERMS
from invoice_payment_summary import payment_view

def install(app,provider,session,enabled,root,failure):
    def gate(payload=None,admin=False):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if (admin and me.get('role')!='admin') or not allowed(me,'invoices',payload):raise failure('ACCESS_DENIED',403)
        return rec
    def rpc(payload):
        rec=gate(payload);r=parse(provider.call('/rest/v1/rpc/custom_u_invoices_114',rec['token'],{'payload':payload},limit=1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'QUOTE_NOT_FOUND':404,'INVOICE_LOCKED':409,'VERSION_CONFLICT':409,'ID_CONFLICT':409,'FINALISED_QUOTE_REQUIRED':409}.get(r['error'],400))
        me=provider.access(rec['token'])
        if not allowed(me,'invoices',payload):raise failure('ACCESS_DENIED',403)
        if payload.get('op')=='get':
            try:r['payment_view']=payment_view(r['data'],r['payment_summary'])
            except (ValueError,KeyError,TypeError):raise failure('INVOICE_PAYMENTS_UNAVAILABLE',503) from None
        return r
    @app.get('/invoices')
    def invoice_page():return app.response_class((root/'static/invoices.html').read_bytes(),mimetype='text/html')
    @app.get('/invoices.js')
    def invoice_script():return app.response_class((root/'static/invoices.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/invoices')
    def invoice_listing():return jsonify(rpc({'op':'list','q':request.args.get('q',''),'page':request.args.get('page','1')}))
    @app.get('/api/invoices/sources')
    def invoice_sources():
        rec=gate({'op':'sources'});op=request.args.get('op','setup');payload={'op':op}
        if op=='customers':payload.update(q=request.args.get('q',''),page=request.args.get('page','1'))
        elif op=='customer':payload['id']=request.args.get('id','')
        result=parse(provider.call('/rest/v1/rpc/custom_u_invoice_sources_114',rec['token'],{'payload':payload},limit=1000000))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 400)
        if not allowed(provider.access(rec['token']),'invoices',{'op':'sources'}):raise failure('ACCESS_DENIED',403)
        return jsonify(result)
    @app.get('/api/invoices/defaults')
    def invoice_defaults():gate();return jsonify(terms=INVOICE_TERMS)
    @app.get('/api/invoices/customer-terms/<quote_id>')
    def invoice_customer_terms(quote_id):
        from staff_access import can
        rec=gate({'op':'create'})
        if not can(provider.access(rec['token']),'invoices.create'):raise failure('ACCESS_DENIED',403)
        result=parse(provider.call('/rest/v1/rpc/custom_u_invoice_terms_113',rec['token'],{'quote_id':quote_id},limit=10000))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 400)
        if not can(provider.access(rec['token']),'invoices.create'):raise failure('ACCESS_DENIED',403)
        return jsonify(result)
    @app.get('/api/invoices/<ident>')
    def invoice_detail(ident):return jsonify(rpc({'op':'get','id':ident}))
    @app.post('/api/invoices/save')
    def invoice_save():
        gate();request.max_content_length=262144;body=request.get_json()
        if isinstance(body,dict) and body.get('op') not in ('create_direct','save_direct','amend') and request.content_length and request.content_length>32768:raise failure('INVALID_REQUEST',413)
        if not isinstance(body,dict) or body.get('op') not in ('create','save','issue','create_direct','save_direct','amend','convert'):raise failure('INVALID_REQUEST',400)
        if body.get('op')=='convert':body={**body,'terms':INVOICE_TERMS}
        return jsonify(rpc(body))
    @app.get('/invoices/<ident>/print')
    def invoice_printable(ident):
        result=rpc({'op':'get','id':ident})
        return app.response_class(render_invoice(result['data'],result['payment_summary']),mimetype='text/html')

    @app.get('/api/invoices/<ident>/pdf')
    def invoices_download(ident):
        from document_downloads import pdf_response
        result=rpc({'op':'get','id':ident})
        return pdf_response(app,'invoice',result['data'],result['payment_summary'])

    @app.get('/invoices/<ident>/source-quote/print')
    def invoice_source_printable(ident):
        from quote_print import render_quote
        invoice=rpc({'op':'get','id':ident})['data']
        if invoice['quote_id'] is None:raise failure('NOT_FOUND',404)
        quote=dict(invoice['quote_snapshot'])
        if 'original_quote_data' in quote:quote['data']=quote.pop('original_quote_data')
        return app.response_class(render_quote(quote),mimetype='text/html')
