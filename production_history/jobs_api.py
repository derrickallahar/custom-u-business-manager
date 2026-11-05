"""Private job routes. SQL repeats access, approval, deposit and version checks."""
from flask import request,jsonify
from staff_access import allowed
from workspace_codec import parse

def install(app,provider,session,enabled,root,failure):
    def rpc(payload):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if not allowed(me,'jobs',payload):raise failure('ACCESS_DENIED',403)
        result=parse(provider.call('/rest/v1/rpc/custom_u_jobs_103',rec['token'],{'payload':payload},limit=2*1024*1024))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],{'ACCESS_DENIED':403,'NOT_FOUND':404,'VERSION_CONFLICT':409,'JOB_LOCKED':409,'INVALID_TRANSITION':409}.get(result['error'],400))
        if not allowed(provider.access(rec['token']),'jobs',payload):raise failure('ACCESS_DENIED',403)
        return jsonify(result)
    @app.get('/jobs')
    def jobs_page():return app.response_class((root/'static/jobs.html').read_bytes(),mimetype='text/html')
    @app.get('/jobs.js')
    def jobs_script():return app.response_class((root/'static/jobs.js').read_bytes(),mimetype='text/javascript')
    def query(op):
        mode=request.args.get('mode','test')
        if mode not in ('test','live'):raise failure('INVALID_REQUEST',400)
        return {'op':op,'q':request.args.get('q',''),'page':request.args.get('page','1'),'status':request.args.get('status',''),'is_test':mode=='test'}
    @app.get('/api/jobs')
    def jobs_list():return rpc(query('list'))
    @app.get('/api/jobs/sources')
    def jobs_sources():return rpc(query('sources'))
    @app.get('/api/jobs/<ident>')
    def job_detail(ident):return rpc({'op':'get','id':ident})
    @app.post('/api/jobs/save')
    def job_save():
        request.max_content_length=16000;body=request.get_json()
        if not isinstance(body,dict) or body.get('op') not in ('create','save','transition','reopen'):raise failure('INVALID_REQUEST',400)
        return rpc(body)
