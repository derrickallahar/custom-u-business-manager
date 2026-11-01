"""Custom U v0.7.7 — fictional-only cloud staging entry point.

Fail closed if cloud deployment consent, TLS CA, HTTPS origin, or fake-data checks
are missing. No schema creation, SMTP, or data migration happens at startup.
"""
from __future__ import annotations

import base64
import binascii
import os
import pathlib
import re
import sys
import tempfile
from urllib.parse import urlsplit

from pilot_core import SCHEMA, PilotError
from staff_auth import StaffStore


class DeploymentError(Exception):
    pass


def required_environment(environment=None):
    env = os.environ if environment is None else environment
    if env.get('CUSTOMU_STAGING_ONLY') != 'YES_FICTIONAL_ONLY':
        raise DeploymentError('FICTIONAL_STAGING_CONFIRMATION_REQUIRED')
    if env.get('CUSTOMU_ENABLE_CLOUD') != 'RUN_FICTIONAL_PILOT':
        raise DeploymentError('CLOUD_TEST_CONFIRMATION_REQUIRED')
    origin = env.get('CUSTOMU_PUBLIC_ORIGIN', '').strip().rstrip('/')
    u = urlsplit(origin)
    if (u.scheme != 'https' or not u.hostname or u.username or u.password
            or u.path or u.query or u.fragment or not u.netloc
            or not re.fullmatch(r'[A-Za-z0-9.-]+(?::443)?', u.netloc)):
        raise DeploymentError('PUBLIC_HTTPS_ORIGIN_REQUIRED')
    dsn = env.get('CUSTOMU_STAGING_DATABASE_URL', '').strip()
    pg = urlsplit(dsn)
    if (pg.scheme not in ('postgres', 'postgresql') or not pg.username
            or not pg.password or not pg.hostname or not pg.path.endswith('/postgres')
            or not pg.hostname.endswith('.pooler.supabase.com')):
        raise DeploymentError('SUPABASE_STAGING_SESSION_POOLER_URI_REQUIRED')
    ca_b64 = env.get('CUSTOMU_PG_CA_B64', '').strip()
    if not ca_b64 or len(ca_b64) > 300_000:
        raise DeploymentError('CA_CERTIFICATE_B64_REQUIRED')
    csrf_key = decode_csrf_key(env.get('CUSTOMU_CSRF_KEY_B64', '').strip())
    return origin, dsn, ca_b64, csrf_key


def decode_csrf_key(b64):
    # Per-deployment 256-bit random key, stored as an encrypted runtime secret.
    # Remains identical across container restarts and additional instances.
    try:
        key = base64.b64decode(b64, validate=True)
    except (ValueError, binascii.Error):
        raise DeploymentError('INVALID_CSRF_KEY_B64') from None
    if len(key) != 32:
        raise DeploymentError('CSRF_KEY_MUST_BE_32_BYTES')
    return key


def decode_certificate(b64):
    try:
        pem=base64.b64decode(b64,validate=True)
    except (ValueError,binascii.Error):
        raise DeploymentError('INVALID_CA_CERTIFICATE_B64') from None
    if (not pem.startswith(b'-----BEGIN CERTIFICATE-----')
        or b'-----END CERTIFICATE-----' not in pem or len(pem)>200_000):
        raise DeploymentError('INVALID_CA_CERTIFICATE_PEM')
    return pem


def write_ephemeral_certificate(pem):
    # Root CA is public, but never upload the trust file to GitHub. The private
    # staging container receives it through an encrypted runtime environment var.
    path=None
    try:
        with tempfile.NamedTemporaryFile(prefix='customu-pg-root-',suffix='.pem',delete=False) as f:
            path=f.name
            f.write(pem)
        os.chmod(path,0o600)
        return path
    except Exception:
        if path:
            pathlib.Path(path).unlink(missing_ok=True)
        raise DeploymentError('CA_CERTIFICATE_INSTALL_FAILED') from None


def verify_only_fictional_data(store):
    # This gate is intentionally narrow and only permits the v0.7.6 test schema.
    if SCHEMA != 'custom_u_permissions_pilot_076':
        raise DeploymentError('UNEXPECTED_DATABASE_SCHEMA')
    with store.connection() as conn:
        with conn.cursor() as c:
            c.execute(f'''SELECT COUNT(*) AS n FROM "{SCHEMA}"."users"
                           WHERE email !~* '^[a-z0-9_.+\\-]+@example\\.invalid$' ''')
            if c.fetchone()['n']:
                raise DeploymentError('NON_FICTIONAL_STAFF_RECORD_DETECTED')
            c.execute(f'''SELECT COUNT(*) AS n FROM "{SCHEMA}"."users"
                           WHERE role='admin' AND active=1''')
            if not c.fetchone()['n']:
                raise DeploymentError('ACTIVE_FICTIONAL_ADMIN_REQUIRED')
            c.execute(f'''SELECT COUNT(*) AS n FROM "{SCHEMA}"."customers"
                           WHERE name NOT LIKE 'TEST %%'
                             AND name NOT LIKE 'SYNTH %%'
                             AND name NOT LIKE 'FICTIONAL %%' ''')
            if c.fetchone()['n']:
                raise DeploymentError('NON_FICTIONAL_CUSTOMER_RECORD_DETECTED')
            for table in ('users','customers','customer_contacts','catalogs','quotes','invoices'):
                # Identifiers are restricted to this hard-coded list.
                column = 'email' if table in ('users','customers','customer_contacts') else 'recipient_email'
                c.execute(f'''SELECT COUNT(*) AS n FROM "{SCHEMA}"."{table}"
                               WHERE "{column}" IS NOT NULL AND "{column}" <> ''
                                 AND "{column}" !~* '^[a-z0-9_.+\\-]+@example\\.invalid$' ''')
                if c.fetchone()['n']:
                    raise DeploymentError('NON_FICTIONAL_EMAIL_RECORD_DETECTED')


def main():
    ca_path=None
    try:
        origin,dsn,ca_b64,csrf_key=required_environment()
        ca_path=write_ephemeral_certificate(decode_certificate(ca_b64))
        store=StaffStore(dsn,ca_path)
        verify_only_fictional_data(store)
        from cloud_server import run
        run(store,origin,csrf_key)
    except (DeploymentError,PilotError) as exc:
        print('CLOUD STAGING STOPPED:',str(exc),file=sys.stderr)
        sys.exit(1)
    except Exception:
        # NEVER print DSN, DB password, environment values or stack traces.
        print('CLOUD STAGING STOPPED: DATABASE_OR_CONFIGURATION_ERROR',file=sys.stderr)
        sys.exit(1)
    finally:
        if ca_path:
            pathlib.Path(ca_path).unlink(missing_ok=True)


if __name__=='__main__':
    main()
