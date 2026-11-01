"""Private fictional test-object gateway; no keys sent to clients.

Optional in v0.7.8, and never automatically creates a bucket or makes
one public. The storage service key is permitted ONLY in cloud runtime.
"""
from __future__ import annotations
import base64, binascii, hashlib, json, os, re, secrets
from urllib import request, parse, error
from pilot_core import PilotError

BUCKET='custom-u-fictional-private'
MAX_BYTES=2_000_000
MIME={'application/pdf': '.pdf','image/png':'.png','image/jpeg':'.jpg'}


def validate_safe_name(name,mime):
    if not isinstance(name,str) or not re.fullmatch(r'TEST_[A-Za-z0-9_.-]{1,85}',name):
        raise PilotError('ONLY_TEST_FILENAMES_ALLOWED')
    if mime not in MIME or not name.lower().endswith(('.jpg','.jpeg') if mime=='image/jpeg' else MIME[mime]):
        raise PilotError('FILE_TYPE_NOT_ALLOWED')


def validate_upload(data):
    if not isinstance(data,dict):raise PilotError('INVALID_UPLOAD')
    name=data.get('filename')
    mime=data.get('mime')
    encoded=data.get('base64')
    validate_safe_name(name,mime)
    if not isinstance(encoded,str) or len(encoded)>((MAX_BYTES+2)//3)*4+4:
        raise PilotError('FILE_TOO_LARGE',413)
    try:contents=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):raise PilotError('INVALID_FILE_ENCODING') from None
    if not 1<=len(contents)<=MAX_BYTES:raise PilotError('FILE_TOO_LARGE',413)
    if mime=='application/pdf' and not contents.startswith(b'%PDF-'):
        raise PilotError('FILE_CONTENT_MISMATCH')
    if mime=='image/png' and not contents.startswith(b'\x89PNG\r\n\x1a\n'):
        raise PilotError('FILE_CONTENT_MISMATCH')
    if mime=='image/jpeg' and not contents.startswith(b'\xff\xd8\xff'):
        raise PilotError('FILE_CONTENT_MISMATCH')
    return name,mime,contents

class StorageClient:
    def __init__(self,url,key):
        url=url.strip().rstrip('/')
        if not re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co',url):
            raise ValueError('SUPABASE_STORAGE_URL_INVALID')
        if not isinstance(key,str) or len(key)<30 or any(c.isspace() for c in key):
            raise ValueError('SUPABASE_STORAGE_SERVER_KEY_INVALID')
        self.url=url;self._key=key

    def _call(self,method,path,contents=None,mime='application/json',max_download=MAX_BYTES):
        # All paths constructed from constants or random alphanumeric object keys.
        req=request.Request(self.url+'/storage/v1'+path,method=method,
            headers={'apikey':self._key,'Authorization':'Bearer '+self._key,
                     'Content-Type':mime,'Cache-Control':'no-store'},data=contents)
        try:
            with request.urlopen(req,timeout=20) as resp:
                data=resp.read(max_download+1)
                if len(data)>max_download:raise PilotError('STORAGE_RESPONSE_TOO_LARGE',502)
                return data
        except (error.URLError,TimeoutError) as exc:
            raise PilotError('STORAGE_SERVICE_UNAVAILABLE',502) from None

    def confirm_private_bucket(self):
        data=self._call('GET','/bucket/'+BUCKET,max_download=50000)
        try:
            info=json.loads(data)
            if info.get('id')!=BUCKET or info.get('public') is not False:
                raise PilotError('STORAGE_BUCKET_NOT_PRIVATE',503)
        except (ValueError,AttributeError,TypeError):
            raise PilotError('STORAGE_BUCKET_CONFIGURATION_INVALID',503) from None

    def save(self,data,mime):
        self.confirm_private_bucket()
        key='pilot078/'+secrets.token_hex(18)+MIME[mime]
        self._call('POST','/object/'+BUCKET+'/'+key,data,mime,max_download=20000)
        return key

    def read(self,key):
        self.confirm_private_bucket()
        if not isinstance(key,str) or not re.fullmatch(r'pilot078/[a-f0-9]{36}\.(?:pdf|png|jpg)',key):
            raise PilotError('INVALID_STORAGE_OBJECT',400)
        return self._call('GET','/object/authenticated/'+BUCKET+'/'+key,max_download=MAX_BYTES)

    def delete_orphan(self,key):
        # Only if PostgreSQL metadata creation failed immediately after upload.
        if not re.fullmatch(r'pilot078/[a-f0-9]{36}\.(?:pdf|png|jpg)',key):return
        try:self._call('DELETE','/object/'+BUCKET+'/'+key,max_download=20000)
        except PilotError:pass  # orphan may require manual cleanup
