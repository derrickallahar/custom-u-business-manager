"""Administrator management of existing confirmed accounts, without invitations."""
from flask import request,jsonify
from workspace_codec import parse

def install(app,provider,session,enabled,root,failure):
    def rpc(payload):
        rec,me=session()
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        r=parse(provider.call('/rest/v1/rpc/custom_u_staff_102',rec['token'],{'payload':payload},limit=1024*1024))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],{'ACCESS_DENIED':403,'ADMIN_PROTECTED':403,'VERSION_CONFLICT':409,'ALREADY_ADDED':409,'NOT_FOUND':404}.get(r['error'],400))
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return jsonify(r)
    @app.get('/staff')
    def staff_page():return app.response_class((root/'static/staff.html').read_bytes(),mimetype='text/html')
    @app.get('/staff.js')
    def staff_script():return app.response_class((root/'static/staff.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/staff')
    def staff_list():return rpc({'op':'list'})
    @app.post('/api/staff/save')
    def staff_save():
        request.max_content_length=8192
        body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('add','save'):raise failure('INVALID_REQUEST',400)
        return rpc(body)
