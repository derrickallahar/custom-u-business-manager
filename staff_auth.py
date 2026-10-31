"""Fictional-only staff login, per-user DB sessions and role checks for pilot v0.7.6.

NOT a production-ready identity provider. Bind to loopback only. Never use real staff
names, mailbox addresses or customer information in this pilot.
"""
from __future__ import annotations
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets

from pilot_core import Store, PilotError, SCHEMA, now, short_text, positive_id

ITERATIONS = 600_000
MAX_STAFF = 5
MAX_FAILURES = 5
LOCK_MINUTES = 10
SESSION_HOURS = 8
ALLOWED_ROLES = ('admin', 'sales', 'office', 'production')
_current_actor: ContextVar[int | None] = ContextVar('custom_u_current_actor', default=None)


def valid_password(value):
    if not isinstance(value, str) or not 14 <= len(value) <= 128 or value.isspace() or any(ord(c) < 32 for c in value):
        raise PilotError('PASSWORD_MUST_HAVE_14_TO_128_CHARACTERS')
    return value


def password_hash(password):
    valid_password(password)
    salt = secrets.token_bytes(24)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}'


def password_verify(password, encoded):
    try:
        name, count, salt, digest = encoded.split('$')
        n = int(count)
        if name != 'pbkdf2_sha256' or n < 600_000 or n > 1_500_000 or len(salt) != 48 or len(digest) != 64:
            return False
        if not isinstance(password, str) or len(password) > 128:
            return False
        check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), n)
        return hmac.compare_digest(check, bytes.fromhex(digest))
    except (ValueError, TypeError, AttributeError):
        return False


# A constant-time fallback when the account does not exist. Never store a default password.
_FALLBACK = password_hash('Fictional-No-Such-Account-Only')


def staff_email(value):
    if not isinstance(value, str):
        raise PilotError('INVALID_STAFF_EMAIL')
    v = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_.+\-]+@example\.invalid', v) or len(v) > 160:
        raise PilotError('ONLY_FICTIONAL_STAFF_EMAIL_ALLOWED')
    return v


# Every permission is enforced on the server on EACH request. Role defaults may be
# overridden for an individual non-admin staff member: allow, deny, or inherit.
# Staff account administration is reserved to administrators and cannot be granted.
PERMISSION_GROUPS = (
    ('customers.view','Customers: view'),
    ('customers.create','Customers: create and add contacts'),
    ('products.view','Products: view'),
    ('catalogs.view','Catalog Studio: view'),
    ('catalogs.create','Catalog Studio: create'),
    ('quotes.view','Quotes: view'),
    ('quotes.create','Quotes: create'),
    ('quotes.approve','Quotes: approve (creates invoice and job)'),
    ('invoices.view','Invoices: view'),
    ('invoices.issue','Invoices: issue test invoices'),
    ('payments.record','Payments: record test payments'),
    ('jobs.view','Production: view'),
    ('jobs.update','Production: update stage'),
)
PERMISSION_KEYS = tuple(k for k,_ in PERMISSION_GROUPS)
ROLE_DEFAULTS = {
    'admin': set(PERMISSION_KEYS),
    'sales': {'customers.view','customers.create','products.view','catalogs.view','catalogs.create',
              'quotes.view','quotes.create','quotes.approve','jobs.view'},
    'office': set(PERMISSION_KEYS),
    'production': {'jobs.view','jobs.update'},
}

def effective_permissions(role, overrides=None):
    if role not in ALLOWED_ROLES:
        return {k:False for k in PERMISSION_KEYS}
    # Admin is an immutable superuser of this LOCAL staging pilot.
    if role == 'admin':
        return {k:True for k in PERMISSION_KEYS}
    result = {k:k in ROLE_DEFAULTS[role] for k in PERMISSION_KEYS}
    for k,v in (overrides or {}).items():
        if k in result and type(v) is bool:
            result[k]=v
    return result


def role_allowed(role, group):
    """Legacy helper for tests/documentation; request handlers use live per-user permissions."""
    alias={'dashboard':'jobs.view','customers':'customers.view','products':'products.view',
           'catalogs':'catalogs.view','quotes':'quotes.view','approve_quote':'quotes.approve',
           'invoices':'invoices.view','payment':'payments.record',
           'jobs':'jobs.view','jobs_write':'jobs.update'}
    if group == 'staff':return role == 'admin'
    return effective_permissions(role).get(alias.get(group,group),False)


class StaffStore(Store):
    """Separate schema, PostgreSQL sessions; audit actors belong to the current request."""

    def actor_id(self, cursor):
        uid = _current_actor.get()
        if uid is None:
            raise PilotError('ACTOR_CONTEXT_REQUIRED', 500)
        return uid

    def login(self, email, password):
        email = staff_email(email)
        if not isinstance(password, str) or len(password) > 128:
            return None
        result = None
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''INSERT INTO "{SCHEMA}"."pilot_login_attempts"(email,failures)
                              VALUES(%s,0) ON CONFLICT(email) DO NOTHING''', (email,))
                c.execute(f'''SELECT failures,locked_until FROM "{SCHEMA}"."pilot_login_attempts"
                              WHERE email=%s FOR UPDATE''', (email,))
                rec = c.fetchone()
                blocked = rec['locked_until'] is not None and rec['locked_until'] > datetime.now(timezone.utc)
                c.execute(f'''SELECT id,email,full_name,role,active,password_hash
                              FROM "{SCHEMA}"."users" WHERE email=%s''', (email,))
                user = c.fetchone()
                good = password_verify(password, user['password_hash'] if user else _FALLBACK)
                if not good or blocked or not user or not user['active']:
                    fails = min(100, rec['failures'] + 1)
                    locked = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)) if fails >= MAX_FAILURES else None
                    c.execute(f'''UPDATE "{SCHEMA}"."pilot_login_attempts" SET failures=%s,locked_until=%s
                                  WHERE email=%s''', (fails,locked,email))
                else:
                    c.execute(f'''UPDATE "{SCHEMA}"."pilot_login_attempts" SET failures=0,locked_until=NULL
                                  WHERE email=%s''',(email,))
                    token = secrets.token_urlsafe(36)
                    digest = hashlib.sha256(token.encode()).hexdigest()
                    c.execute(f'''INSERT INTO "{SCHEMA}"."pilot_sessions" (token_hash,user_id,expires_at)
                                  VALUES(%s,%s,%s)''',(digest,user['id'],datetime.now(timezone.utc)+timedelta(hours=SESSION_HOURS)))
                    result = (token, {**{k:user[k] for k in ('id','email','full_name','role')}, 'permissions':self.permissions_in_cursor(c,user['id'],user['role'])})
        return result

    def session(self, token):
        if not isinstance(token,str) or len(token) > 256:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''SELECT u.id,u.email,u.full_name,u.role
                              FROM "{SCHEMA}"."pilot_sessions" AS s
                              JOIN "{SCHEMA}"."users" AS u ON u.id=s.user_id
                              WHERE s.token_hash=%s AND s.expires_at > NOW() AND u.active=1''',(digest,))
                user=c.fetchone()
                if user:
                    user['permissions']=self.permissions_in_cursor(c,user['id'],user['role'])
                return user

    @staticmethod
    def permissions_in_cursor(c, user_id, role):
        if role == 'admin':return effective_permissions(role)
        c.execute(f"""SELECT permission_key,allowed FROM "{SCHEMA}"."staff_permission_overrides"
                     WHERE user_id=%s""",(user_id,))
        overrides={x['permission_key']:x['allowed'] for x in c.fetchall()}
        return effective_permissions(role,overrides)

    def staff_permissions(self, target_id):
        target_id=positive_id(target_id)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id,role,full_name,active FROM "{SCHEMA}"."users" WHERE id=%s',(target_id,))
                user=c.fetchone()
                if not user:raise PilotError('STAFF_NOT_FOUND',404)
                c.execute(f"""SELECT permission_key,allowed FROM "{SCHEMA}"."staff_permission_overrides"
                             WHERE user_id=%s""",(target_id,))
                overrides={row['permission_key']:bool(row['allowed']) for row in c.fetchall()}
                return {'user':user,'defaults':effective_permissions(user['role']),
                        'overrides':overrides,'effective':effective_permissions(user['role'],overrides)}

    def set_staff_permissions(self, target_id, overrides, actor):
        target_id=positive_id(target_id)
        if not isinstance(overrides,dict):raise PilotError('INVALID_PERMISSIONS')
        if len(overrides)>len(PERMISSION_KEYS) or any(k not in PERMISSION_KEYS or type(v) is not bool
                                                     for k,v in overrides.items()):
            raise PilotError('INVALID_PERMISSION_OVERRIDE')
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id,role,active FROM "{SCHEMA}"."users" WHERE id=%s FOR UPDATE',(target_id,))
                target=c.fetchone()
                if not target:raise PilotError('STAFF_NOT_FOUND',404)
                if target['role']=='admin':raise PilotError('ADMIN_PERMISSIONS_CANNOT_BE_OVERRIDDEN',409)
                if not target['active']:raise PilotError('INACTIVE_USER_CANNOT_BE_EDITED',409)
                c.execute(f'DELETE FROM "{SCHEMA}"."staff_permission_overrides" WHERE user_id=%s',(target_id,))
                for key,allowed in overrides.items():
                    c.execute(f"""INSERT INTO "{SCHEMA}"."staff_permission_overrides"
                        (user_id,permission_key,allowed,changed_by) VALUES (%s,%s,%s,%s)""",
                        (target_id,key,allowed,actor))
                c.execute(f"""INSERT INTO "{SCHEMA}"."audit"
                    (actor_user_id,action,entity,entity_id,metadata,created_at)
                    VALUES (%s,'update_staff_permissions','user',%s,%s,%s)""",
                    (actor,target_id,__import__('json').dumps({'synthetic':True,'overrides':overrides}),now()))
        return {'id':target_id,'effective':effective_permissions(target['role'],overrides)}

    def logout(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'DELETE FROM "{SCHEMA}"."pilot_sessions" WHERE token_hash=%s',(digest,))

    def staff(self):
        return self.read('users','id,email,full_name,role,active,created_at','id ASC',20)

    def create_staff(self, data, actor):
        email = staff_email(data.get('email'))
        name = short_text(data.get('full_name'),100)
        role = data.get('role')
        if role not in ALLOWED_ROLES:
            raise PilotError('INVALID_STAFF_ROLE')
        hashed = password_hash(data.get('password'))
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id FROM "{SCHEMA}"."users" WHERE active=1 FOR UPDATE')
                active_users = c.fetchall()
                if len(active_users) >= MAX_STAFF:
                    raise PilotError('PILOT_STAFF_LIMIT_REACHED',409)
                c.execute(f'SELECT id FROM "{SCHEMA}"."users" WHERE email=%s',(email,))
                if c.fetchone():
                    raise PilotError('STAFF_ACCOUNT_EXISTS',409)
                c.execute(f'''INSERT INTO "{SCHEMA}"."users"
                              (email,full_name,password_hash,role,active,created_at)
                              VALUES(%s,%s,%s,%s,1,%s) RETURNING id''',
                          (email,name,hashed,role,now()))
                new_id = c.fetchone()['id']
                c.execute(f'''INSERT INTO "{SCHEMA}"."audit"(actor_user_id,action,entity,entity_id,metadata,created_at)
                              VALUES(%s,'create_staff','user',%s,'{{"synthetic":true}}',%s)''',(actor,new_id,now()))
        return {'id':new_id,'email':email,'role':role}

    def deactivate_staff(self, target_id, actor):
        target_id=positive_id(target_id)
        if target_id == actor:
            raise PilotError('CANNOT_DEACTIVATE_SELF',409)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id,role,active FROM "{SCHEMA}"."users" WHERE id=%s FOR UPDATE',(target_id,))
                user=c.fetchone()
                if not user:
                    raise PilotError('STAFF_NOT_FOUND',404)
                if user['active']:
                    if user['role']=='admin':
                        c.execute(f'''SELECT id FROM "{SCHEMA}"."users" WHERE role='admin' AND active=1 FOR UPDATE''')
                        if len(c.fetchall()) <= 1:
                            raise PilotError('CANNOT_DEACTIVATE_LAST_ADMIN',409)
                    c.execute(f'UPDATE "{SCHEMA}"."users" SET active=0 WHERE id=%s',(target_id,))
                    c.execute(f'DELETE FROM "{SCHEMA}"."pilot_sessions" WHERE user_id=%s',(target_id,))
                    c.execute(f'''INSERT INTO "{SCHEMA}"."audit"(actor_user_id,action,entity,entity_id,metadata,created_at)
                                  VALUES(%s,'deactivate_staff','user',%s,'{{"synthetic":true}}',%s)''',(actor,target_id,now()))
        return {'id':target_id,'active':False}

    def assign_job(self, job_id, staff_id, actor):
        job_id = positive_id(job_id)
        staff_id = positive_id(staff_id)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id FROM "{SCHEMA}"."users" WHERE id=%s AND active=1',(staff_id,))
                if not c.fetchone(): raise PilotError('STAFF_NOT_FOUND',404)
                c.execute(f'SELECT id FROM "{SCHEMA}"."jobs" WHERE id=%s FOR UPDATE',(job_id,))
                if not c.fetchone(): raise PilotError('JOB_NOT_FOUND',404)
                c.execute(f'UPDATE "{SCHEMA}"."jobs" SET assigned_to_user_id=%s,updated_at=%s WHERE id=%s',
                          (staff_id,now(),job_id))
                c.execute(f'''INSERT INTO "{SCHEMA}"."audit"(actor_user_id,action,entity,entity_id,metadata,created_at)
                              VALUES(%s,'assign_job','job',%s,'{{"synthetic":true}}',%s)''',(actor,job_id,now()))
        return {'job_id':job_id,'assigned_to_user_id':staff_id}
