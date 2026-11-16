"""Administrator scheduling UI; automatic execution belongs to the private job."""
import os,json
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import request,jsonify,make_response
from email_delivery import checked_pdf,identifier
from reminder_rules import settings,day
from reminder_worker import Runner,ReminderError

def install(app,provider,session,enabled,root,failure):
    app.extensions['reminder_runner_factory']=lambda:Runner(provider)
    def gate():
        rec,me=session()
        if not enabled or me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec,me
    def check(rec):
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
    def mode(value):
        if value not in ('test','live'):raise failure('INVALID_MODE',400)
        return value
    def call(rec,payload):
        result=json.loads(provider.call('/rest/v1/rpc/custom_u_reminders_112',rec['token'],{'payload':payload},limit=10000000))
        if not isinstance(result,dict):raise failure('REMINDER_RESPONSE_INVALID',503)
        if result.get('error'):raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 409)
        check(rec);return result
    def live_ready():return os.getenv('CUSTOMU_REMINDER_LIVE_ENABLED','')=='1' and os.getenv('CUSTOMU_EMAIL_TEST_MODE','1')=='0'
    def current_date():return datetime.now(ZoneInfo('America/Nassau')).date().isoformat()
    def state(rec,chosen,asof):
        try:day(asof)
        except (ValueError,TypeError):raise failure('INVALID_DATE',400) from None
        return call(rec,{'op':'state','mode':chosen,'as_of':asof})
    @app.get('/reminders')
    def reminders_page():return app.response_class((root/'static/reminders.html').read_bytes(),mimetype='text/html')
    @app.get('/reminders.js')
    def reminders_script():return app.response_class((root/'static/reminders.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/reminders')
    def reminders_state():
        rec,me=gate();result=state(rec,mode(request.args.get('mode','test')),request.args.get('as_of',current_date()))
        return jsonify(**result,live_enabled=live_ready(),test_recipient=os.getenv('CUSTOMU_EMAIL_TEST_RECIPIENT','derrick@custom-u.com'),build='112')
    @app.post('/api/reminders/settings')
    def reminders_save():
        request.max_content_length=200000;rec,_=gate();data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'mode','expected_version','settings'}:raise failure('INVALID_REQUEST',400)
        chosen=mode(data['mode'])
        try:settings(data['settings'],False)
        except (ValueError,TypeError,KeyError):raise failure('INVALID_SCHEDULE',400) from None
        if chosen=='live' and data['settings']['enabled'] and not live_ready():raise failure('REMINDER_LIVE_DISABLED',409)
        return jsonify(call(rec,{'op':'save',**data}))
    @app.get('/api/reminders/preview')
    def reminders_preview():
        rec,_=gate();chosen=mode(request.args.get('mode','test'));result=state(rec,chosen,request.args.get('as_of',current_date()))
        found=next((c for c in result['candidates'] if c['invoice']['id']==request.args.get('id') and c['invoice']['source']==request.args.get('source')),None)
        if not found or found['stage'] is None or found['invoice']['balance_cents']<=0:raise failure('REMINDER_NOT_DUE',409)
        try:packet=app.extensions['reminder_runner_factory']().packet(found,result['as_of'],chosen)
        except (ValueError,ReminderError):raise failure('REMINDER_PREVIEW_UNAVAILABLE',409) from None
        check(rec);return jsonify(data=packet,preview_only=True)
    @app.post('/api/reminders/run-test')
    def reminders_run():
        rec,_=gate();data=request.get_json()
        if data!={'confirm':True}:raise failure('REMINDER_CONFIRM_REQUIRED',400)
        try:report=app.extensions['reminder_runner_factory']().run('test',manual=True,access_check=lambda:check(rec),max_count=1)
        except ReminderError as exc:raise failure(str(exc),409) from None
        check(rec);return jsonify(report=report)
    @app.get('/api/reminders/<ident>/pdf')
    def reminders_pdf(ident):
        rec,_=gate()
        try:identifier(ident)
        except ValueError:raise failure('INVALID_REQUEST',400) from None
        row=call(rec,{'op':'get','mode':mode(request.args.get('mode','test')),'id':ident})['data']
        try:raw=checked_pdf(row)
        except ValueError:raise failure('REMINDER_PDF_INVALID',409) from None
        response=make_response(raw);response.headers['Content-Type']='application/pdf';response.headers['Content-Disposition']='inline; filename="'+row['pdf_filename']+'"';return response
