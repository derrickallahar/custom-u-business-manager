"""Authenticated read-only account statements and receivables reports."""
import re
from flask import request,jsonify
from workspace_codec import parse
from statement_rules import build,report
from statement_print import render_statement,render_receivables

def install(app,provider,session,enabled,root,failure):
    def fetch(customer=None):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        allowed={'mode'} if customer else {'mode','q','status','page'}
        if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args):raise failure('INVALID_REQUEST',400)
        mode=request.args.get('mode','live')
        if mode not in ('live','test'):raise failure('INVALID_MODE',400)
        payload={'op':'statement' if customer else 'receivables','test_mode':mode=='test'}
        if customer:
            if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',customer):raise failure('INVALID_ID',400)
            payload['customer_id']=customer
        raw=parse(provider.call('/rest/v1/rpc/custom_u_statements_101',rec['token'],{'payload':payload},limit=8*1024*1024))
        if not isinstance(raw,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in raw:raise failure(raw['error'],{'ACCESS_DENIED':403,'NO_ISSUED_INVOICES':404,'INVALID_REQUEST':400,'INVALID_ID':400}.get(raw['error'],409))
        if customer and raw.get('customer_id')!=customer:raise failure('INVALID_REPORT_RESPONSE')
        try:data=build(raw,mode=='test')
        except (ValueError,KeyError,TypeError,OverflowError):raise failure('INVALID_REPORT_RESPONSE') from None
        provider.access(rec['token'])
        return data
    def listing():
        data=fetch()
        try:
            page=request.args.get('page','1')
            if not re.fullmatch(r'[1-9][0-9]{0,5}',page):raise ValueError()
            return report(data,request.args.get('q',''),request.args.get('status','all'),int(page))
        except ValueError:raise failure('INVALID_REPORT_FILTER',400) from None
    @app.get('/statements')
    def statements_page():return app.response_class((root/'static/statements.html').read_bytes(),mimetype='text/html')
    @app.get('/statements.js')
    def statements_script():return app.response_class((root/'static/statements.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/statements')
    def statements_report():
        data=listing();data.pop('all_customers');return jsonify(data)
    @app.get('/api/statements/customer/<customer>')
    def statements_customer(customer):return jsonify(fetch(customer))
    @app.get('/statements/customer/<customer>/print')
    def statement_print(customer):return app.response_class(render_statement(fetch(customer)),mimetype='text/html')
    @app.get('/statements/report/print')
    def statements_report_print():
        data=listing()
        if len(data['all_customers'])>500:raise failure('PRINT_LIMIT_USE_FILTER',409)
        return app.response_class(render_receivables(data),mimetype='text/html')
