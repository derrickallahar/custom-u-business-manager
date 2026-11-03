"""Custom U v0.7.8: HTTPS proxy-hosted FICTIONAL data cloud staging.

Runs only after explicit environment and database checks in cloud_main.
NOT APPROVED FOR REAL EMPLOYEES, CUSTOMERS, FILES, OR PAYMENTS.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit
import hashlib, hmac, json, os
from private_storage import validate_upload, MAX_BYTES
from pilot_core import PilotError, SCHEMA, positive_id
from staff_auth import StaffStore, _current_actor, role_allowed

ROOT=Path(__file__).resolve().parent
PORT=int(os.getenv("PORT", "8080"))
COOKIE="__Host-cu_staging_077"
# Do not generate a per-process signing secret: App Platform can restart
# or replace the process while a user's browser session is still valid.
MAX_BODY=24*1024

class PilotServer(ThreadingHTTPServer):
    allow_reuse_address=True
    daemon_threads=True
    def __init__(self,address,store,public_origin,csrf_key,storage=None):
        if not isinstance(csrf_key, bytes) or len(csrf_key)!=32:
            raise ValueError('INVALID_CSRF_SIGNING_KEY')
        self.csrf_key=csrf_key
        from urllib.parse import urlsplit
        parsed=urlsplit(public_origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("HTTPS_PUBLIC_ORIGIN_REQUIRED")
        self.public_origin="https://"+parsed.netloc.lower()
        self.public_host=parsed.netloc.lower()
        super().__init__(address,Handler)
        self.store=store
        self.storage=storage
        from history_archive import Archive
        self.history=Archive(storage)

class Handler(BaseHTTPRequestHandler):
    server_version='CustomUCloudStaging/0.8.9'
    sys_version=''
    def log_message(self,*args):
        pass  # no URLs, cookies, staff names, passwords or payloads in console logs
    def send_headers(self, status=200, mime='application/json; charset=utf-8', extra=None, length=0):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(length))
        for k,v in {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                    'X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
                    'Cross-Origin-Resource-Policy':'same-origin',
                    'Strict-Transport-Security':'max-age=86400',
                    'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
                    'X-Robots-Tag':'noindex, nofollow, noarchive',
                    'Vary':'Cookie',
                    'Content-Security-Policy':"default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"}.items():
            self.send_header(k,v)
        if extra:
            for k,v in extra.items():self.send_header(k,v)
        self.end_headers()
    def json(self,value,status=200,extra=None):
        b=json.dumps(value,ensure_ascii=False,default=str).encode('utf-8')
        self.send_headers(status,extra=extra,length=len(b));self.wfile.write(b)
    def fail(self,code,status=400):
        self.json({'error':code},status)
    def path_only(self):return urlsplit(self.path).path
    def origin_ok(self, require_origin=False):
        # The frontend and Host header must match the bound HTTPS App Platform URL.
        # DO terminates HTTPS in front of this HTTP container. Never use arbitrary
        # X-Forwarded-Host or X-Forwarded-Proto from the untrusted request.
        host=self.headers.get('Host','').strip().lower()
        if host != self.server.public_host:
            return False
        origin=self.headers.get('Origin','')
        if require_origin:
            return origin == self.server.public_origin
        return not origin or origin == self.server.public_origin
    def cookie_token(self):
        try:
            c=SimpleCookie(self.headers.get('Cookie',''))
            token=c[COOKIE].value
            return token if len(token)<256 else ''
        except (KeyError,ValueError):
            return ''
    def user(self):
        token=self.cookie_token()
        if not token:return None
        return self.server.store.session(token)
    def csrf_token(self):
        return hmac.new(self.server.csrf_key,self.cookie_token().encode(),hashlib.sha256).hexdigest()
    def csrf_ok(self):
        return hmac.compare_digest(self.headers.get('X-CustomU-CSRF',''),self.csrf_token())
    def json_body(self, max_body=MAX_BODY):
        try:
            size=int(self.headers.get('Content-Length','-1'))
            if not 2<=size<=max_body:raise PilotError('INVALID_REQUEST_SIZE',413)
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise ValueError()
            return data
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            raise PilotError('INVALID_JSON') from None
    def authorized(self,user,scope):
        if scope=='staff':
            if user['role']!='admin':raise PilotError('ACCESS_DENIED',403)
        elif not user['permissions'].get(scope,False):
            raise PilotError('ACCESS_DENIED',403)
    def do_GET(self):
        if self.path_only() == '/healthz':
            return self.json({'status':'ok','mode':'fictional-staging'})
        if self.path_only() == '/robots.txt':
            data=b'User-agent: *\nDisallow: /\n'
            self.send_headers(mime='text/plain; charset=utf-8',length=len(data))
            self.wfile.write(data)
            return
        if not self.origin_ok():return self.fail('INVALID_HOST',403)
        path=self.path_only()
        if path in ('/','/app.js','/style.css'):
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path]
            mime={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[name]
            data=(ROOT/'static'/name).read_bytes()
            self.send_headers(mime=mime,length=len(data));self.wfile.write(data);return
        try:
            user=self.user()
            if not user:raise PilotError('LOGIN_REQUIRED',401)
            if path in ('/history', '/history.js', '/api/history-preview', '/api/history') or path.startswith('/api/history/'):
                self.authorized(user,'staff')
                if path in ('/api/history','/api/history-preview'):
                    return self.json(self.server.history.listing(urlsplit(self.path).query))
                if path.startswith('/api/history/records/'):
                    return self.json({'data':self.server.history.detail(path.removeprefix('/api/history/records/'))})
                if path.startswith('/api/history/files/'):
                    name,data=self.server.history.pdf(path.removeprefix('/api/history/files/'))
                    self.send_headers(mime='application/pdf',length=len(data),extra={'Content-Disposition':'attachment; filename="'+name+'"'})
                    self.wfile.write(data);return
                if path not in ('/history','/history.js'):raise PilotError('NOT_FOUND',404)
                name='history.html' if path=='/history' else 'history.js'
                data=(ROOT/'static'/name).read_bytes()
                mime='text/html; charset=utf-8' if path=='/history' else 'text/javascript; charset=utf-8'
                self.send_headers(mime=mime,length=len(data));self.wfile.write(data);return
            if path.startswith('/documents/'):
                parts=path.split('/')
                if len(parts)!=4 or parts[2] not in ('quotes','invoices'):
                    raise PilotError('NOT_FOUND',404)
                kind=parts[2]
                self.authorized(user,kind+'.view')
                ident=positive_id(int(parts[3]))
                record=next((r for r in getattr(self.server.store,kind)() if r['id']==ident),None)
                if record is None:raise PilotError('NOT_FOUND',404)
                from hosted_documents import render_document
                data=render_document(kind,record)
                self.send_headers(mime='text/html; charset=utf-8',length=len(data));self.wfile.write(data);return
            if path=='/api/session':
                return self.json({'authenticated':True,'me':user,'csrf':self.csrf_token(),'schema':SCHEMA})
            if path=='/api/private-files':
                self.authorized(user,'files.view')
                return self.json({'data':self.server.store.private_files(),
                                  'storage_enabled':self.server.storage is not None})
            if path.startswith('/api/private-files/') and path.endswith('/download'):
                self.authorized(user,'files.view')
                if self.server.storage is None:raise PilotError('STORAGE_NOT_CONFIGURED',503)
                f=self.server.store.private_file(positive_id(int(path.split('/')[3])))
                # Metadata should be known-safe even if manually edited in DB.
                from private_storage import validate_safe_name
                validate_safe_name(f['original_name'],f['mime'])
                content=self.server.storage.read(f['object_key'])
                if len(content)!=f['size_bytes'] or hashlib.sha256(content).hexdigest()!=f['sha256']:
                    raise PilotError('FILE_INTEGRITY_CHECK_FAILED',502)
                # The name is restricted to safe ASCII at upload, so no header injection.
                self.send_headers(mime='application/octet-stream',length=len(content),extra={
                    'Content-Disposition':f'attachment; filename="{f["original_name"]}"'})
                self.wfile.write(content)
                return
            if path=='/api/audit-summary':
                self.authorized(user,'staff')
                return self.json({'data':self.server.store.audit_summary()})
            if path=='/api/permission-catalog':
                self.authorized(user,'staff')
                from staff_auth import PERMISSION_GROUPS, ROLE_DEFAULTS
                return self.json({'data':{'permissions':[{'key':k,'label':label} for k,label in PERMISSION_GROUPS],
                                          'roles':{role:sorted(keys) for role,keys in ROLE_DEFAULTS.items()}}})
            if path.startswith('/api/staff/') and path.endswith('/permissions'):
                self.authorized(user,'staff')
                return self.json({'data':self.server.store.staff_permissions(positive_id(int(path.split('/')[3])))})
            if path=='/api/dashboard':
                # All authenticated staff can view the dashboard.
                # Minimize data per user. Never expose invoice totals unless invoices.view is granted.
                raw=self.server.store.dashboard()
                data={}
                if user['permissions']['jobs.view']:data['jobs']=raw['jobs']
                for key,perm in [('customers','customers.view'),('products','products.view'),
                                 ('catalogs','catalogs.view'),('quotes','quotes.view'),('invoices','invoices.view')]:
                    if user['permissions'][perm]:data[key]=raw[key]
                if user['permissions']['invoices.view']:
                    data['open_cents']=raw['open_cents'];data['invoice_cents']=raw['invoice_cents']
                return self.json({'data':data})
            endpoints={'/api/customers':('customers','customers.view'),
                '/api/products':('products','products.view'),'/api/catalogs':('catalogs','catalogs.view'),
                '/api/quotes':('quotes','quotes.view'),'/api/invoices':('invoices','invoices.view'),
                '/api/jobs':('jobs','jobs.view'),'/api/staff':('staff','staff')}
            if path in endpoints:
                fn,scope=endpoints[path]
                self.authorized(user,scope)
                data=getattr(self.server.store,fn)()
                if fn=='jobs' and not user['permissions']['quotes.view']:
                    # Jobs carry quote line prices in legacy ticket JSON. Strip them for
                    # production-only users rather than leaking prices via job API.
                    for job in data:
                        ticket=json.loads(job.get('ticket_json') or '{}')
                        for line in ticket.get('lines',[]):
                            if isinstance(line,dict):line.pop('unit_cents',None)
                        job['ticket_json']=json.dumps(ticket)
                return self.json({'data':data})
            if path.startswith('/api/customers/') and path.endswith('/contacts'):
                self.authorized(user,'customers.view')
                return self.json({'data':self.server.store.contacts(positive_id(int(path.split('/')[3])))})
            raise PilotError('NOT_FOUND',404)
        except PilotError as e:return self.fail(e.code,e.status)
        except (ValueError,IndexError):return self.fail('INVALID_ID')
        except Exception:return self.fail('DATABASE_REQUEST_FAILED',502)
    def do_POST(self):
        if not self.origin_ok(require_origin=True):return self.fail('INVALID_HOST_OR_ORIGIN',403)
        if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':
            return self.fail('JSON_CONTENT_TYPE_REQUIRED',415)
        try:
            path=self.path_only()
            body=self.json_body(max_body=2_850_000 if path=='/api/private-files' else MAX_BODY)
            if path=='/api/login':
                user=self.server.store.login(body.get('email'),body.get('password'))
                if user is None:raise PilotError('INVALID_LOGIN_OR_TEMPORARILY_LOCKED',403)
                token,me=user
                return self.json({'result':{'logged_in':True,'me':me}},extra={
                    'Set-Cookie':f'{COOKIE}={token}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
            user=self.user()
            if not user:raise PilotError('LOGIN_REQUIRED',401)
            if path=='/api/history' or path.startswith('/api/history/'):
                self.authorized(user,'staff')
                raise PilotError('HISTORY_READ_ONLY',405)
            if not self.csrf_ok():raise PilotError('CSRF_REJECTED',403)
            if path=='/api/logout':
                self.server.store.logout(self.cookie_token())
                return self.json({'result':'logged_out'},extra={'Set-Cookie':f'{COOKIE}=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            # All audit rows from Store have this authenticated actor identity, even on concurrent threads.
            t=_current_actor.set(user['id'])
            try:
                result=self.mutate(path,body,user)
            finally:
                _current_actor.reset(t)
            return self.json({'result':result},201)
        except PilotError as e:return self.fail(e.code,e.status)
        except (ValueError,IndexError):return self.fail('INVALID_REQUEST')
        except Exception:return self.fail('DATABASE_REQUEST_FAILED',502)
    def mutate(self,path,body,user):
        s=self.server.store
        if path=='/api/private-files':
            self.authorized(user,'files.upload')
            if self.server.storage is None:raise PilotError('STORAGE_NOT_CONFIGURED',503)
            name,mime,contents=validate_upload(body)
            key=self.server.storage.save(contents,mime)
            try:return s.save_private_file(key,name,mime,contents,user['id'])
            except Exception:
                self.server.storage.delete_orphan(key)
                raise
        if path=='/api/staff':self.authorized(user,'staff');return s.create_staff(body,user['id'])
        if path.startswith('/api/staff/') and path.endswith('/permissions'):
            self.authorized(user,'staff');return s.set_staff_permissions(positive_id(int(path.split('/')[3])),body.get('overrides'),user['id'])
        if path.startswith('/api/staff/') and path.endswith('/deactivate'):
            self.authorized(user,'staff');return s.deactivate_staff(positive_id(int(path.split('/')[3])),user['id'])
        if path=='/api/customers':self.authorized(user,'customers.create');return s.add_customer(body)
        if path.startswith('/api/customers/') and path.endswith('/contacts'):
            self.authorized(user,'customers.create');return s.add_contact(positive_id(int(path.split('/')[3])),body)
        if path=='/api/catalogs':self.authorized(user,'catalogs.create');return s.add_catalog(body)
        if path=='/api/quotes':self.authorized(user,'quotes.create');return s.add_quote(body.get('catalog_id'))
        if path.startswith('/api/quotes/') and path.endswith('/approve'):
            self.authorized(user,'quotes.approve');return s.approve_quote(positive_id(int(path.split('/')[3])))
        if path.startswith('/api/invoices/') and path.endswith('/issue'):
            self.authorized(user,'invoices.issue')
            if body.get('confirm')!='ISSUE SYNTHETIC':raise PilotError('CONFIRM_SYNTHETIC_ISSUE')
            return s.issue_invoice(positive_id(int(path.split('/')[3])))
        if path.startswith('/api/invoices/') and path.endswith('/payments'):
            self.authorized(user,'payments.record');return s.record_payment(positive_id(int(path.split('/')[3])),body.get('amount_cents'))
        if path.startswith('/api/jobs/') and path.endswith('/stage'):
            self.authorized(user,'jobs.update');return s.set_job_stage(positive_id(int(path.split('/')[3])),body.get('stage'))
        if path.startswith('/api/jobs/') and path.endswith('/assign'):
            self.authorized(user,'staff');return s.assign_job(positive_id(int(path.split('/')[3])),body.get('staff_id'),user['id'])
        raise PilotError('NOT_FOUND',404)

def run(store,public_origin,csrf_key,storage=None):
    if not 1024 <= PORT <= 65535:
        raise ValueError('INVALID_HTTP_PORT')
    with PilotServer(('0.0.0.0',PORT),store,public_origin,csrf_key,storage) as server:
        print('Custom U v0.7.8 — FICTIONAL cloud staging, app started. No customer emails.')
        print('Public address configured. Never use real Custom U customer or employee data.')
        try:server.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass
