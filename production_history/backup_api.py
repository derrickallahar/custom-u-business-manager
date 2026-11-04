"""Authenticated encrypted download. Never writes snapshot or passphrase to disk."""
from datetime import datetime, timezone
import hashlib, threading, time
from flask import request, make_response
from backup_codec import MAX_BYTES, encrypt, parse, passphrase_bytes

def install(app,provider,session,enabled,failure):
    lock=threading.Lock();last={}
    @app.post('/api/customers/backup')
    def crm_backup():
        rec,me=session()
        if not enabled:raise failure('CUSTOMERS_NOT_ENABLED',409)
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'passphrase'}:raise failure('INVALID_REQUEST',400)
        password=data['passphrase']
        try:passphrase_bytes(password)
        except ValueError:raise failure('PASSPHRASE_LENGTH',400) from None
        if not lock.acquire(blocking=False):raise failure('BACKUP_BUSY',429)
        try:
            now=time.monotonic();identity=me['email']
            if now-last.get(identity,-100)<30:raise failure('BACKUP_WAIT_30_SECONDS',429)
            last.clear();last[identity]=now
            raw=provider.call('/rest/v1/rpc/custom_u_crm_snapshot_094',rec['token'],{},limit=MAX_BYTES)
            snapshot=parse(raw)
            if not isinstance(snapshot,dict):raise failure('INVALID_BACKUP_RESPONSE')
            if 'error' in snapshot:
                raise failure(snapshot['error'],403 if snapshot['error']=='ACCESS_DENIED' else 503)
            if snapshot.get('format')!='custom-u-crm-snapshot-094' or not isinstance(snapshot.get('records'),list) or not isinstance(snapshot.get('audit'),list):raise failure('INVALID_BACKUP_RESPONSE')
            # Membership may have been revoked while a larger snapshot was being fetched.
            provider.access(rec['token'])
            encrypted=encrypt(raw,password)
            filename='CustomU_CRM_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+hashlib.sha256(encrypted).hexdigest()[:8]+'.cucrm'
            response=make_response(encrypted)
            response.headers['Content-Type']='application/octet-stream'
            response.headers['Content-Disposition']='attachment; filename="'+filename+'"'
            return response
        finally:
            password=None;data=None
            lock.release()
