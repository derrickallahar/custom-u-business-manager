"""Course reading, server-graded tests and HR training management."""
import csv, io, re
from flask import request, jsonify, make_response
from workspace_codec import parse
from training_pdf import guide_pdf

READ = {'list', 'get', 'report'}
WRITE = {'save', 'publish', 'archive', 'assign', 'read', 'submit'}

def install(app, provider, session, enabled, root, failure):
    def rpc(payload, limit=8*1024*1024):
        rec, me = session()
        if not enabled: raise failure('CUSTOMERS_NOT_ENABLED',409)
        result = parse(provider.call('/rest/v1/rpc/custom_u_training_127', rec['token'], {'payload':payload}, limit=limit))
        if not isinstance(result,dict): raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            code=result['error'];raise failure(code,403 if code=='ACCESS_DENIED' else 404 if code=='NOT_FOUND' else 409)
        after=provider.access(rec['token'])
        if after.get('user_id')!=me.get('user_id') or after.get('role')!=me.get('role'): raise failure('ACCESS_DENIED',403)
        return result
    @app.get('/hr/training')
    @app.get('/hr/training/new')
    @app.get('/hr/training/<uuid:ident>')
    @app.get('/hr/training/<uuid:ident>/edit')
    def training_page(ident=None):
        return app.response_class((root/'static/training.html').read_bytes(),mimetype='text/html')
    @app.get('/training.js')
    def training_script():return app.response_class((root/'static/training.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/training')
    def training_read():
        payload=request.args.to_dict()
        if payload.get('op') not in READ: raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(payload))
    @app.post('/api/training/action')
    def training_action():
        session();request.max_content_length=240000;payload=request.get_json()
        if not isinstance(payload,dict) or payload.get('op') not in WRITE: raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(payload))
    @app.get('/api/training/<uuid:ident>/guide.pdf')
    def training_guide(ident):
        result=rpc({'op':'get','id':str(ident)})
        # The employee guide never includes the answer key, even for managers.
        raw=guide_pdf(result['course']['data'])
        response=make_response(raw);response.headers['Content-Type']='application/pdf'
        response.headers['Content-Disposition']='attachment; filename="CustomU_Training_Guide.pdf"'
        return response
    @app.get('/api/training/<uuid:ident>/answer-key.pdf')
    def training_key(ident):
        if rpc({'op':'list'}).get('manager') is not True: raise failure('ACCESS_DENIED',403)
        result=rpc({'op':'get','id':str(ident)})
        if any('correct_index' not in q for q in result['course']['data']['questions']): raise failure('ACCESS_DENIED',403)
        response=make_response(guide_pdf(result['course']['data'],answer_key=True));response.headers['Content-Type']='application/pdf'
        response.headers['Content-Disposition']='attachment; filename="CustomU_Training_Answer_Key.pdf"'
        return response
    @app.get('/api/training/<uuid:ident>/results.csv')
    def training_results(ident):
        result=rpc({'op':'report','id':str(ident)});out=io.StringIO(newline='');writer=csv.writer(out)
        writer.writerow(['Course','Edition','Employee','Active account','Assigned','Due date','Status','Lessons read','Best score percent','Attempts','Started Nassau','Completed Nassau'])
        def safe(v):
            s=str(v) if v is not None else ''
            return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s
        def date(v):
            if not v:return ''
            from datetime import datetime
            from zoneinfo import ZoneInfo
            return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(ZoneInfo('America/Nassau')).isoformat()
        for row in result['rows']:
            p=row['progress'] or {}
            writer.writerow([safe(result['course']['title']),safe(result['course']['edition']),safe(row['email']),row['active'],row['assigned'],row['due_date'],
             'Completed' if p.get('completed_at') else 'In progress' if p else 'Not started',len(p.get('read_lessons',[])),p.get('best_score',''),row['attempt_count'],date(p.get('started_at')),date(p.get('completed_at'))])
        response=make_response(out.getvalue().encode('utf-8-sig'));response.headers['Content-Type']='text/csv; charset=utf-8'
        response.headers['Content-Disposition']='attachment; filename="CustomU_Training_Results.csv"';return response
