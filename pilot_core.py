"""Custom U v0.7.6 synthetic-only PostgreSQL staff pilot data layer.

The operational SQLite app is deliberately NOT imported. No customer mail,
ShopVox data, artwork uploads, admin password hashes or real invoice issuance.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import re
import secrets
from typing import Any

SCHEMA = 'custom_u_permissions_pilot_076'
VERIFIED_SOURCE = 'custom_u_synthetic_073'
BASE = Path(__file__).resolve().parent
STAGES = ('new', 'design', 'proof', 'production', 'installation', 'completed', 'on_hold')
METHODS = ('UV Printing', 'Laser Engraving', 'DTF Printing', 'Embroidery', 'Unbranded')

class PilotError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code, self.status = code, status


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def amount_cents(value: Any, *, max_cents=100_000_000):
    if type(value) is not int or value < 0 or value > max_cents:
        raise PilotError('INVALID_AMOUNT')
    return value


def quantity(value: Any):
    if type(value) is not int or not 1 <= value <= 10000:
        raise PilotError('INVALID_QUANTITY')
    return value


def short_text(value: Any, limit=160):
    if not isinstance(value, str):
        raise PilotError('INVALID_TEXT')
    val = value.strip()
    if not val or len(val) > limit or any(ord(c) < 32 for c in val):
        raise PilotError('INVALID_TEXT')
    return val


def test_customer_name(value: Any):
    value = short_text(value, 120)
    if not value.upper().startswith(('TEST ', 'SYNTH ', 'FICTIONAL ')):
        raise PilotError('ONLY_FICTIONAL_CUSTOMERS_ALLOWED')
    return value


def test_email(value: Any):
    if not isinstance(value, str):
        raise PilotError('INVALID_EMAIL')
    val = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_.+\-]+@(?:[a-z0-9\-]+\.)*example\.invalid', val):
        raise PilotError('ONLY_EXAMPLE_INVALID_EMAIL_ALLOWED')
    return val


def pg_connect(dsn: str, cert: str):
    # Imports are delayed; the user's existing v0.7.2 pg_venv provides psycopg.
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise PilotError('POSTGRES_DRIVER_MISSING',500) from None
    return psycopg.connect(dsn, sslmode='verify-full', sslrootcert=cert,
                           connect_timeout=15, row_factory=dict_row)


def verify_tls(conn):
    try:
        p = conn.info.get_parameters()
    except (AttributeError, TypeError):
        raise PilotError('TLS_SETTINGS_UNAVAILABLE',500) from None
    if p.get('sslmode','').lower() != 'verify-full' or not p.get('sslrootcert'):
        raise PilotError('TLS_VERIFICATION_REQUIRED',500)


def qualified(table: str):
    from psycopg import sql
    if table not in {
        'users','customers','customer_contacts','products','catalogs','quotes',
        'invoices','payments','jobs','audit'
    }:
        raise PilotError('INVALID_TABLE',500)
    return sql.Identifier(SCHEMA, table)


def qid(column: str):
    from psycopg import sql
    return sql.Identifier(column)


def setup(dsn: str, cert: str, confirm: str, admin_hash: str):
    if confirm != 'CREATE ISOLATED V076 STAFF PILOT':
        raise PilotError('CONSENT_REQUIRED')
    if not (isinstance(admin_hash,str) and admin_hash.startswith('pbkdf2_sha256$')):
        raise PilotError('ADMIN_PASSWORD_HASH_REQUIRED')
    ddl=(BASE / 'schema_template.sql').read_text(encoding='utf-8')
    if 'CREATE SCHEMA "custom_u_permissions_pilot_076"' not in ddl or 'custom_u_synthetic_073' in ddl:
        raise PilotError('SCHEMA_TEMPLATE_INVALID',500)
    with pg_connect(dsn,cert) as conn:
        verify_tls(conn)
        with conn.cursor() as cur:
            cur.execute('SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)',(VERIFIED_SOURCE,))
            if not cur.fetchone()['exists']:
                raise PilotError('VERIFIED_SYNTHETIC_SOURCE_SCHEMA_REQUIRED')
            # Confirm this is the previously verified fictional staging project.
            cur.execute('''SELECT total_cents,paid_cents
                           FROM "custom_u_synthetic_073"."invoices"
                           WHERE number=%s''', ('SYNTH-I-001',))
            source_invoice=cur.fetchone()
            if not source_invoice or (source_invoice['total_cents'],source_invoice['paid_cents'])!=(10000,2500):
                raise PilotError('EXPECTED_SYNTHETIC_STAGING_DATA_NOT_FOUND')
            cur.execute('SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)',(SCHEMA,))
            if cur.fetchone()['exists']:
                raise PilotError('PILOT_SCHEMA_ALREADY_EXISTS',409)
            # All schema statements plus fictional seeds are ONE transaction.
            # Execute separately for compatibility with psycopg 3 and pooler
            # extended-protocol statement preparation. The trusted template
            # contains no semicolons within SQL string literals.
            for statement in ddl.split(';\n'):
                statement = statement.strip().removesuffix(';')
                if statement and any(not l.lstrip().startswith('--') for l in statement.splitlines()):
                    cur.execute(statement)
            timestamp=now()
            cur.execute('''INSERT INTO "custom_u_permissions_pilot_076"."users"
              (email,full_name,password_hash,role,active,created_at)
              VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',
              ('admin@example.invalid','Fictional Administrator',
               admin_hash,'admin',1,timestamp))
            actor=cur.fetchone()['id']
            cur.execute('''INSERT INTO "custom_u_permissions_pilot_076"."customers"
              (name,email,phone,terms_days,created_at)
              VALUES(%s,%s,%s,%s,%s) RETURNING id''',
              ('TEST Pilot Customer','buyer@example.invalid','000-000-0000',30,timestamp))
            cust=cur.fetchone()['id']
            cur.execute('''INSERT INTO "custom_u_permissions_pilot_076"."customer_contacts"
              (customer_id,source_contact_id,first_name,last_name,email,is_primary,is_billing)
              VALUES(%s,%s,%s,%s,%s,1,1)''',
              (cust,'PILOT-DEFAULT','Fictional','Buyer','buyer@example.invalid'))
            cur.execute('''INSERT INTO "custom_u_permissions_pilot_076"."products"
              (sku,name,category,description,base_cents,base_cost_cents,methods_json,colors_json,active,created_at)
              VALUES (%s,%s,%s,%s,%s,0,%s,%s,1,%s)''',
              ('PILOT-JOURNAL','Fictional Executive Journal','corporate-gifts',
               'Fictional item for cloud database testing only',2500,
               json.dumps(['UV Printing','Laser Engraving']),
               json.dumps(['black','navy']),timestamp))
    return {'result':'CREATED','schema':SCHEMA,'source_untouched':True}


class Store:
    def __init__(self, dsn: str, cert: str):
        self.dsn, self.cert=dsn, cert

    @contextmanager
    def connection(self):
        with pg_connect(self.dsn,self.cert) as conn:
            verify_tls(conn)
            with conn.cursor() as c:
                c.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(SCHEMA,))
                if not c.fetchone():
                    raise PilotError('PILOT_SCHEMA_NOT_INITIALIZED',409)
            yield conn

    def read(self, table: str, columns: str, order='id DESC', limit=100):
        # Columns and ordering are hard-coded by server, never user-supplied.
        from psycopg import sql
        with self.connection() as conn:
            with conn.cursor() as c:
                stmt=sql.SQL('SELECT '+columns+' FROM {} ORDER BY '+order+' LIMIT %s').format(qualified(table))
                c.execute(stmt,(limit,))
                return c.fetchall()

    def dashboard(self):
        with self.connection() as conn:
            with conn.cursor() as c:
                out={}
                for table in ('customers','products','catalogs','quotes','invoices','jobs'):
                    c.execute('SELECT COUNT(*) AS n FROM '+ f'"{SCHEMA}"."{table}"')
                    out[table]=c.fetchone()['n']
                c.execute(f'''SELECT COALESCE(SUM(total_cents),0) AS invoice_cents,
                          COALESCE(SUM(GREATEST(total_cents-paid_cents,0)),0) AS open_cents
                          FROM "{SCHEMA}"."invoices"''')
                out.update(c.fetchone())
                return out

    def customers(self):
        return self.read('customers','id,name,email,phone,terms_days,created_at','id DESC')

    def contacts(self, cust_id: int):
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''SELECT id,first_name,last_name,email,is_primary,is_billing
                   FROM "{SCHEMA}"."customer_contacts" WHERE customer_id=%s ORDER BY id''',(cust_id,))
                return c.fetchall()

    def products(self):
        return self.read('products','id,name,sku,category,base_cents,methods_json,colors_json,description','id DESC')

    def catalogs(self):
        return self.read('catalogs','id,title,customer_id,recipient_name,lines_json,status,created_at','id DESC')

    def quotes(self):
        return self.read('quotes','id,number,customer_id,catalog_id,status,total_cents,lines_json,created_at','id DESC')

    def invoices(self):
        return self.read('invoices','id,number,customer_id,quote_id,status,total_cents,paid_cents,due_date,created_at','id DESC')

    def jobs(self):
        return self.read('jobs','id,number,customer_id,quote_id,status,title,ticket_json,assigned_to_user_id,created_at','id DESC')

    def add_customer(self, data):
        name=test_customer_name(data.get('name'))
        email=test_email(data.get('email'))
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''INSERT INTO "{SCHEMA}"."customers"
                  (name,email,phone,terms_days,created_at)
                  VALUES(%s,%s,%s,30,%s) RETURNING id''',
                  (name,email,'',now()))
                cust=c.fetchone()['id']
                self.audit(c,'create','customer',cust)
        return {'id':cust,'name':name}

    def add_contact(self, cust_id, data):
        first=short_text(data.get('first_name'),80)
        last=short_text(data.get('last_name'),80)
        email=test_email(data.get('email'))
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id FROM "{SCHEMA}"."customers" WHERE id=%s',(cust_id,))
                if not c.fetchone(): raise PilotError('CUSTOMER_NOT_FOUND',404)
                c.execute(f'''INSERT INTO "{SCHEMA}"."customer_contacts"
                  (customer_id,source_contact_id,first_name,last_name,email)
                  VALUES(%s,%s,%s,%s,%s) RETURNING id''',
                  (cust_id,'P076-'+secrets.token_hex(8),first,last,email))
                val=c.fetchone()['id'];self.audit(c,'create','contact',val)
        return {'id':val}

    def add_catalog(self,data):
        cust_id=positive_id(data.get('customer_id'))
        prod_id=positive_id(data.get('product_id'))
        count=quantity(data.get('quantity'))
        logo_location=short_text(data.get('logo_location','Cover center'),80)
        method=short_text(data.get('method'),80)
        price=amount_cents(data.get('unit_cents'))
        title=short_text(data.get('title'),120)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id,name,email FROM "{SCHEMA}"."customers" WHERE id=%s',(cust_id,))
                cust=c.fetchone()
                if not cust: raise PilotError('CUSTOMER_NOT_FOUND',404)
                c.execute(f'''SELECT id,name,methods_json FROM "{SCHEMA}"."products"
                              WHERE id=%s AND active=1''',(prod_id,))
                p=c.fetchone()
                if not p: raise PilotError('PRODUCT_NOT_FOUND',404)
                if method not in json.loads(p['methods_json']): raise PilotError('BRANDING_METHOD_NOT_AVAILABLE')
                c.execute(f'''SELECT id,first_name,last_name,email FROM "{SCHEMA}"."customer_contacts"
                              WHERE customer_id=%s AND active=1
                              ORDER BY is_primary DESC,id LIMIT 1''',(cust_id,))
                contact=c.fetchone()
                if not contact: raise PilotError('CONTACT_REQUIRED')
                line={'product_id':prod_id,'name':p['name'],'quantity':count,'unit_cents':price,
                      'method':method,'logo_location':logo_location}
                c.execute(f'''INSERT INTO "{SCHEMA}"."catalogs"
                  (customer_id,title,note,lines_json,status,created_by,created_at,
                   recipient_contact_id,recipient_name,recipient_email)
                  VALUES(%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s) RETURNING id''',
                  (cust_id,title,'Synthetic only',json.dumps([line]),self.actor_id(c),now(),
                   contact['id'],f"{contact['first_name']} {contact['last_name']}",contact['email']))
                cat=c.fetchone()['id'];self.audit(c,'create','catalog',cat)
        return {'id':cat,'lines':[line]}

    def add_quote(self, catalog_id):
        catalog_id=positive_id(catalog_id)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''SELECT * FROM "{SCHEMA}"."catalogs" WHERE id=%s FOR UPDATE''',(catalog_id,))
                cat=c.fetchone()
                if not cat: raise PilotError('CATALOG_NOT_FOUND',404)
                lines=json.loads(cat['lines_json']); total=total_from_lines(lines)
                if total <=0: raise PilotError('INVALID_TOTAL')
                n='P076-Q-'+secrets.token_hex(6).upper()
                c.execute(f'''INSERT INTO "{SCHEMA}"."quotes"
                   (number,customer_id,catalog_id,status,lines_json,total_cents,created_by,created_at,
                    recipient_contact_id,recipient_name,recipient_email,subtotal_cents,itemized)
                   VALUES(%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s,%s,%s,1) RETURNING id''',
                   (n,cat['customer_id'],catalog_id,cat['lines_json'],total,self.actor_id(c),now(),
                    cat['recipient_contact_id'],cat['recipient_name'],cat['recipient_email'],total))
                q=c.fetchone()['id'];self.audit(c,'create','quote',q)
        return {'id':q,'number':n,'total_cents':total}

    def approve_quote(self, quote_id):
        quote_id=positive_id(quote_id)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT * FROM "{SCHEMA}"."quotes" WHERE id=%s FOR UPDATE',(quote_id,))
                q=c.fetchone()
                if not q: raise PilotError('QUOTE_NOT_FOUND',404)
                if q['status'] != 'draft':raise PilotError('QUOTE_NOT_DRAFT',409)
                lines=json.loads(q['lines_json'])
                if total_from_lines(lines)!=q['total_cents']:raise PilotError('QUOTE_TOTAL_MISMATCH',409)
                date=now()
                inum='P076-I-'+secrets.token_hex(6).upper()
                jnum='P076-J-'+secrets.token_hex(6).upper()
                due=(datetime.now(timezone.utc).date()+timedelta(days=30)).isoformat()
                c.execute(f'''INSERT INTO "{SCHEMA}"."invoices"
                  (number,customer_id,quote_id,issued_at,due_date,status,total_cents,paid_cents,
                   created_at,recipient_contact_id,recipient_name,recipient_email,
                   lines_json,subtotal_cents,itemized)
                  VALUES(%s,%s,%s,%s,%s,'draft',%s,0,%s,%s,%s,%s,%s,%s,1) RETURNING id''',
                  (inum,q['customer_id'],quote_id,date,due,q['total_cents'],date,q['recipient_contact_id'],
                   q['recipient_name'],q['recipient_email'],q['lines_json'],q['total_cents']))
                invoice_id=c.fetchone()['id']
                ticket={'quote_number':q['number'],'lines':lines,'synthetic_only':True}
                c.execute(f'''INSERT INTO "{SCHEMA}"."jobs"
                   (number,quote_id,customer_id,title,status,created_at,ticket_json,updated_at,workflow_stage)
                   VALUES(%s,%s,%s,%s,'new',%s,%s,%s,'new') RETURNING id''',
                   (jnum,quote_id,q['customer_id'],'Fictional production job',date,json.dumps(ticket),date))
                job_id=c.fetchone()['id']
                c.execute(f'''UPDATE "{SCHEMA}"."quotes" SET status='approved',approved_at=%s
                             WHERE id=%s''',(date,quote_id))
                self.audit(c,'approve','quote',quote_id)
        return {'invoice_id':invoice_id,'invoice_number':inum,'job_id':job_id,'job_number':jnum,
                'status':'CREATED_ATOMICALLY'}

    def issue_invoice(self, invoice_id):
        invoice_id=positive_id(invoice_id)
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id,status FROM "{SCHEMA}"."invoices" WHERE id=%s FOR UPDATE',(invoice_id,))
                row=c.fetchone()
                if not row:raise PilotError('INVOICE_NOT_FOUND',404)
                if row['status']!='draft':raise PilotError('INVOICE_NOT_DRAFT',409)
                c.execute(f'''UPDATE "{SCHEMA}"."invoices" SET status='issued' WHERE id=%s''',(invoice_id,))
                self.audit(c,'issue_synthetic','invoice',invoice_id)
        return {'status':'issued','synthetic_only':True}

    def record_payment(self, invoice_id, amount):
        invoice_id=positive_id(invoice_id)
        amount=amount_cents(amount)
        if amount==0:raise PilotError('INVALID_PAYMENT')
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'''SELECT id,total_cents,paid_cents,status FROM "{SCHEMA}"."invoices"
                  WHERE id=%s FOR UPDATE''',(invoice_id,))
                inv=c.fetchone()
                if not inv:raise PilotError('INVOICE_NOT_FOUND',404)
                if inv['status']!='issued':raise PilotError('INVOICE_NOT_ISSUED',409)
                balance=inv['total_cents']-inv['paid_cents']
                if amount>balance:raise PilotError('PAYMENT_EXCEEDS_BALANCE',409)
                c.execute(f'''INSERT INTO "{SCHEMA}"."payments"
                  (invoice_id,amount_cents,recorded_by,method,reference,paid_on,created_at)
                  VALUES(%s,%s,%s,'synthetic',%s,%s,%s) RETURNING id''',
                  (invoice_id,amount,self.actor_id(c),'PILOT ONLY',datetime.now(timezone.utc).date().isoformat(),now()))
                payment_id=c.fetchone()['id']
                c.execute(f'''UPDATE "{SCHEMA}"."invoices" SET paid_cents=paid_cents+%s WHERE id=%s''',
                          (amount,invoice_id))
                self.audit(c,'payment_synthetic','invoice',invoice_id)
        return {'payment_id':payment_id,'outstanding_cents':balance-amount}

    def set_job_stage(self, job_id, stage):
        job_id=positive_id(job_id)
        if stage not in STAGES:raise PilotError('INVALID_JOB_STAGE')
        with self.connection() as conn:
            with conn.cursor() as c:
                c.execute(f'SELECT id FROM "{SCHEMA}"."jobs" WHERE id=%s FOR UPDATE',(job_id,))
                if not c.fetchone():raise PilotError('JOB_NOT_FOUND',404)
                c.execute(f'''UPDATE "{SCHEMA}"."jobs" SET status=%s,workflow_stage=%s,updated_at=%s
                  WHERE id=%s''',(stage,stage,now(),job_id))
                self.audit(c,'update_stage','job',job_id)
        return {'status':stage}

    def actor_id(self,c):
        c.execute(f'''SELECT id FROM "{SCHEMA}"."users" WHERE email=%s''',
                  ('pilot-operator@example.invalid',))
        r=c.fetchone()
        if not r:raise PilotError('SYNTHETIC_ACTOR_MISSING',500)
        return r['id']

    def audit(self,c,action,entity,item_id):
        c.execute(f'''INSERT INTO "{SCHEMA}"."audit"
          (actor_user_id,action,entity,entity_id,metadata,created_at)
          VALUES(%s,%s,%s,%s,%s,%s)''',
          (self.actor_id(c),action,entity,item_id,'{"synthetic":true}',now()))


def positive_id(v):
    if type(v) is not int or v <= 0 or v > 10**12:raise PilotError('INVALID_ID')
    return v


def total_from_lines(lines):
    if not isinstance(lines,list) or len(lines)==0 or len(lines)>100:raise PilotError('INVALID_LINES')
    total=0
    for line in lines:
        total += quantity(line.get('quantity')) * amount_cents(line.get('unit_cents'))
        if total>10**10:raise PilotError('TOTAL_LIMIT_EXCEEDED')
    return total
