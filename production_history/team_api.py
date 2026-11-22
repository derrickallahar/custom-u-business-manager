"""Team messaging and employee files; every request uses the existing staff device gate."""
import base64,hashlib,io,re
from urllib.parse import quote
from flask import request,jsonify,make_response
from PIL import Image
from workspace_codec import parse
from team_rules import checked_file

PRIVATE={'profile','document','audit','profile_save','document_add','document_active','board_save'}
READ={'status','directory','profile','document','audit','board','messages'}
WRITE={'submit_identifiers','profile_save','document_add','document_active','board_save','ack_board','send','read'}

def install(app,provider,session,enabled,root,failure):
    def rpc(p,limit=8*1024*1024):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        def call(payload):
            r=parse(provider.call('/rest/v1/rpc/custom_u_team_116',rec['token'],{'payload':payload},limit=limit))
            if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
            if 'error' in r:raise failure(r['error'],403 if r['error']=='ACCESS_DENIED' else 404 if r['error']=='NOT_FOUND' else 409)
            return r
        result=call(p)
        after=provider.access(rec['token'])
        if after.get('user_id')!=me.get('user_id') or after.get('role')!=me.get('role'):raise failure('ACCESS_DENIED',403)
        if p['op'] in PRIVATE and call({'op':'status'}).get('manager') is not True:raise failure('ACCESS_DENIED',403)
        return result
    @app.get('/team')
    def team_page():return app.response_class((root/'static/team.html').read_bytes(),mimetype='text/html')
    @app.get('/team.js')
    def team_script():return app.response_class((root/'static/team.js').read_bytes(),mimetype='text/javascript')
    @app.get('/team-notifications.js')
    def team_notifications():return app.response_class((root/'static/team-notifications.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/team')
    def team_read():
        p=request.args.to_dict();op=p.get('op')
        if op not in READ-{'document'}:raise failure('INVALID_REQUEST',400)
        return jsonify(rpc(p))
    @app.post('/api/team/action')
    def team_action():
        request.max_content_length=7100000
        # Authorize the session before decoding a potentially large file.
        session();p=request.get_json()
        if not isinstance(p,dict) or p.get('op') not in WRITE:raise failure('INVALID_REQUEST',400)
        if p['op']=='document_add':
            if rpc({'op':'status'}).get('manager') is not True:raise failure('ACCESS_DENIED',403)
            try:
                raw=base64.b64decode(p.get('content_base64',''),validate=True)
                filename=p.get('filename','')
                if not isinstance(filename,str) or len(filename)>180 or re.search(r'[<>:"|?*\x00-\x1f\x7f/\\]',filename):raise ValueError()
                if not 0<len(raw)<=5*1024*1024:raise ValueError()
                suffix=filename.lower().rsplit('.',1)[-1]
                if suffix=='pdf':
                    if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-4096:]:raise ValueError()
                elif suffix in ('png','jpg','jpeg'):
                    with Image.open(io.BytesIO(raw)) as im:
                        if im.format!=('PNG' if suffix=='png' else 'JPEG') or im.width*im.height>40_000_000:raise ValueError()
                        im.verify()
                else:raise ValueError()
            except (ValueError,TypeError,OSError,Image.DecompressionBombError):raise failure('INVALID_EMPLOYEE_FILE',400) from None
        return jsonify(rpc(p))
    @app.get('/api/team/documents/<ident>')
    def employee_document(ident):
        if not re.fullmatch(r'[a-f0-9-]{36}',ident):raise failure('NOT_FOUND',404)
        result=rpc({'op':'document','id':ident})
        try:raw=checked_file(result['data'],result['content_base64'])
        except (ValueError,KeyError,TypeError):raise failure('EMPLOYEE_FILE_INTEGRITY_FAILED',409) from None
        response=make_response(raw);d=result['data']['data']
        response.headers['Content-Type']=d['mime'];response.headers['Content-Disposition']="attachment; filename=\"employee-document\"; filename*=UTF-8''"+quote(d['filename'],safe='')
        response.headers['X-Content-Type-Options']='nosniff';return response
