"""Authenticated HR actions. Server/DB timestamps; no email or payroll side effects."""
from datetime import datetime,timezone
from flask import request,jsonify,make_response
from workspace_codec import parse,encrypt,passphrase_bytes,MAX_BYTES
from hr_rules import shift_totals,validate_hr
import device_access
import threading
from contextlib import contextmanager

def install(app,provider,session,enabled,root,failure):
    backup_lock=threading.Lock()
    @contextmanager
    def backup_slot():
        if not backup_lock.acquire(blocking=False):raise failure("BACKUP_BUSY",429)
        try:yield
        finally:backup_lock.release()
    def rpc(payload):
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        result=parse(provider.call('/rest/v1/rpc/custom_u_hr_115',rec['token'],{'payload':payload},limit=4*1024*1024))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 409)
        after=provider.access(rec['token'])
        if after.get('user_id')!=me.get('user_id') or after.get('role')!=me.get('role'):raise failure('ACCESS_DENIED',403)
        return result
    @app.get('/hr')
    def hr_page():return app.response_class((root/'static/hr.html').read_bytes(),mimetype='text/html')
    @app.get('/hr.js')
    def hr_script():return app.response_class((root/'static/hr.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/hr')
    def hr_view():
        result=rpc({'op':'view','from':request.args.get('from',''),'to':request.args.get('to','')})
        for row in result['records']:
            if row['kind']=='shift':row['totals']=shift_totals(row['data'],result['now'])
        value=device_access.digest()
        result['current_device_id']=next((r['id'] for r in result['records'] if r['kind']=='device' and r['data']['digest']==value),None)
        result['mobile']=device_access.mobile()
        response=jsonify(result)
        if result['admin'] and not result['mobile']:device_access.ensure_cookie(response)
        return response
    @app.get('/api/hr/timesheet.csv')
    def hr_timesheet():
        import csv,io,json
        result=rpc({'op':'view','from':request.args.get('from',''),'to':request.args.get('to','')})
        names={p['id']:p['email'] for p in result['people']};out=io.StringIO(newline='');writer=csv.writer(out)
        writer.writerow(['Employee','Date','Regular minutes','Overtime minutes','Counted minutes','State','Needs review','Actual clock events','Correction'])
        def safe(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        for row in sorted(result['records'],key=lambda r:(r['data'].get('day',''),r.get('employee_id') or '')):
            if row['kind']!='shift':continue
            if request.args.get('employee') and row['employee_id']!=request.args['employee']:continue
            d=row['data'];totals=shift_totals(d,result['now'])
            writer.writerow([safe(names.get(row['employee_id'],row['employee_id'])),d['day'],totals['regular_minutes'],totals['overtime_minutes'],totals['worked_minutes'],d['state'],totals['needs_review'],safe(json.dumps(d['intervals'])),safe(json.dumps(d['correction']))])
        response=make_response(out.getvalue().encode('utf-8-sig'));response.headers['Content-Type']='text/csv; charset=utf-8';response.headers['Content-Disposition']='attachment; filename="CustomU_Time_Records.csv"';return response
    @app.get('/api/hr/audit/<ident>')
    def hr_audit(ident):return jsonify(rpc({'op':'audit','id':ident}))
    @app.post('/api/hr/action')
    def hr_action():
        request.max_content_length=64000;p=request.get_json()
        if not isinstance(p,dict) or p.get('op') in ('device_save','device_check','view','audit'):raise failure('INVALID_REQUEST',400)
        # Human correction fields are interpreted in the shop's timezone, not the browser's.
        if p.get('op')=='shift_correct':
            from zoneinfo import ZoneInfo
            for field in ('start','end'):
                try:
                    raw=p[field]
                    if not isinstance(raw,str) or len(raw)!=16:raise ValueError()
                    dt=datetime.strptime(raw,'%Y-%m-%dT%H:%M')
                    p[field]=dt.replace(tzinfo=ZoneInfo('America/Nassau')).isoformat()
                except (ValueError,KeyError,TypeError):raise failure('INVALID_HR_DATA',400) from None
        return jsonify(rpc(p))
    @app.post('/api/hr/device')
    def hr_device():
        request.max_content_length=4096;p=request.get_json();_,me=session()
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        if not isinstance(p,dict) or set(p)!={'request_id','name','active','version','id','mobile'} or type(p['mobile']) is not bool:raise failure('INVALID_REQUEST',400)
        if p['id']:
            view=rpc({'op':'view','from':datetime.now().strftime('%Y-%m-01'),'to':datetime.now().strftime('%Y-%m-%d')})
            row=next((r for r in view['records'] if r['kind']=='device' and r['id']==p['id']),None)
            if row is None:raise failure('NOT_FOUND',404)
            dg=row['data']['digest']
        else:
            if device_access.mobile(p['mobile']):raise failure('DESKTOP_REQUIRED',403)
            dg=device_access.digest()
            if not dg:raise failure('DEVICE_COOKIE_REQUIRED',409)
        if p['active'] is True and dg!=device_access.digest():raise failure('APPROVE_ON_COMPUTER',409)
        if p['active'] is True and device_access.mobile(p['mobile']):raise failure('DESKTOP_REQUIRED',403)
        return jsonify(rpc({'op':'device_save','request_id':p['request_id'],'digest':dg,'name':p['name'],'active':p['active'],'version':p['version']}))
    @app.post('/api/hr/backup')
    def hr_backup():
        request.max_content_length=4096
        rec,me=session();p=request.get_json()
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        if not isinstance(p,dict) or set(p)!={'passphrase'}:raise failure('INVALID_REQUEST',400)
        try:passphrase_bytes(p['passphrase'])
        except ValueError:raise failure('PASSPHRASE_LENGTH',400) from None
        with backup_slot():
            raw=provider.call('/rest/v1/rpc/custom_u_hr_snapshot_115',rec['token'],{},limit=MAX_BYTES)
            obj=parse(raw)
            if 'error' in obj:raise failure('ACCESS_DENIED',403)
            try:validate_hr(obj)
            except (ValueError,KeyError,TypeError):raise failure('HR_BACKUP_VALIDATION_FAILED',409) from None
            if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
            from json import dumps
            obj.update(format='custom-u-hr-snapshot-115',exported_at=datetime.now(timezone.utc).isoformat())
            blob=encrypt(dumps(obj,ensure_ascii=False).encode(),p['passphrase']);response=make_response(blob);response.headers['Content-Type']='application/octet-stream';response.headers['Content-Disposition']='attachment; filename="CustomU_HR_115_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.cuhr"';return response
