"""Admin-only legacy ledger. Live import is disabled unless explicitly configured."""
import hashlib,hmac,os,re,time
from flask import request,jsonify
from workspace_codec import parse
from opening_rules import canonical,validate_batch,UUID
from legacy_rules import view,COMMAND_KEYS,clean,cents,day,uid
from legacy_print import printable

def install(app,provider,session,enabled,root,failure):
    def live_allowed():return os.getenv('CUSTOMU_LEGACY_LIVE_IMPORT_ENABLED','')=='1'
    def gate():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec,me
    def rpc(rec,payload,name='custom_u_legacy_111'):
        r=parse(provider.call('/rest/v1/rpc/'+name,rec['token'],{'payload':payload},limit=12_000_000))
        if not isinstance(r,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in r:raise failure(r['error'],403 if r['error']=='ACCESS_DENIED' else 404 if r['error']=='NOT_FOUND' else 409)
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return r
    def checked(state):
        try:return view(state)
        except (ValueError,TypeError,KeyError,OverflowError):raise failure('LEGACY_SAVED_CHECK_FAILED') from None
    def state():
        rec,_=gate()
        if set(request.args)-{'mode','entry'} or any(len(request.args.getlist(k))!=1 for k in request.args):raise failure('INVALID_REQUEST',400)
        mode=request.args.get('mode','test')
        if mode not in ('test','live'):raise failure('INVALID_MODE',400)
        result=rpc(rec,{'op':'state','mode':mode})
        if result.get('mode')!=mode:raise failure('LEGACY_SAVED_CHECK_FAILED')
        return result
    @app.get('/legacy-balances')
    def legacy_page():return app.response_class((root/'static/legacy.html').read_bytes(),mimetype='text/html')
    @app.get('/legacy.js')
    def legacy_script():return app.response_class((root/'static/legacy.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/legacy')
    def legacy_listing():return jsonify(data=checked(state()),live_import_enabled=live_allowed())
    @app.get('/legacy-balances/print')
    def legacy_print_view():
        s=state();checked(s);ident=request.args.get('entry')
        try:html=printable(s,ident)
        except ValueError:raise failure('NOT_FOUND',404) from None
        return app.response_class(html,mimetype='text/html')
    @app.post('/api/legacy/save')
    def legacy_save():
        rec,me=gate();request.max_content_length=16000;command=request.get_json()
        try:
            if not isinstance(command,dict):raise ValueError()
            uid(command['id'])
            if command.get('mode') not in ('test','live') or command.get('confirmed') is not True:raise ValueError()
            if command.get('op')=='import':
                if set(command)!={'op','id','mode','source_id','plan_sha256','review_note','confirmed'}:raise ValueError()
                uid(command['source_id']);clean(command['review_note'],500,10)
                source=rpc(rec,{'op':'get','id':command['source_id']},'custom_u_opening_110')['data'];validate_batch(source)
                if command['plan_sha256']!=source['plan_sha256']:raise failure('LEGACY_SOURCE_CHANGED',409)
                if command['mode']=='live' and not live_allowed():raise failure('LEGACY_LIVE_DISABLED',409)
            else:
                if set(command)!=COMMAND_KEYS or command['op'] not in ('payment','credit','reversal'):raise ValueError()
                uid(command['entry_id']);cents(command['amount_cents'],True);day(command['effective_date']);clean(command['reference'],120);clean(command['reason'],500,3)
                if type(command['expected_version']) is not int or not 0<=command['expected_version']<=5000:raise ValueError()
                if command['op']=='reversal':uid(command['reverses_id'])
                elif command['reverses_id'] is not None:raise ValueError()
        except (KeyError,ValueError,TypeError):raise failure('INVALID_REQUEST',400) from None
        secret=os.getenv('CUSTOMU_EMAIL_SIGNING_SECRET','')
        if not re.fullmatch(r'[a-f0-9]{64}',secret):raise failure('OPENING_SIGNING_SETUP_REQUIRED',409)
        message=canonical({'actor_id':me['user_id'],'expires':int(time.time())+90,'command':command,'live_import_allowed':live_allowed()})
        signature=hmac.new(bytes.fromhex(secret),('legacy111\n'+message).encode(),hashlib.sha256).hexdigest()
        result=rpc(rec,{'op':'signed','message':message,'signature':signature})
        data=checked(result['state'])
        if data['mode']!=command['mode']:raise failure('LEGACY_RESULT_UNCONFIRMED')
        if command['op']=='import':
            if not data['book'] or data['book']['source_id']!=command['source_id'] or data['book']['plan_sha256']!=command['plan_sha256']:raise failure('LEGACY_RESULT_UNCONFIRMED')
        elif not any(e['id']==command['id'] and e['request']==command for row in data['rows'] for e in row['activity']):raise failure('LEGACY_RESULT_UNCONFIRMED')
        return jsonify(existing=result['existing'],data=data,live_import_enabled=live_allowed())
