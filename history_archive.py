"""Read-only archive gateway. No operational database writes."""
import base64, hashlib, json, os, re, threading
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs
from pilot_core import PilotError

MAX_ARCHIVE=10_000_000
MAX_PDF=2_000_000
ID=re.compile(r'[A-Za-z0-9_-]{1,80}')
ROOT=Path(__file__).resolve().parent

def validate(data):
    try:
        if not isinstance(data,bytes) or len(data)>MAX_ARCHIVE:raise ValueError()
        a=json.loads(data)
        if a['format']!='custom-u-history-089' or a['data_class']!='fictional':
            raise ValueError()
        records=a['records'];files=a['files']
        if not isinstance(records,list) or len(records)>20000 or not isinstance(files,dict) or len(files)>100:raise ValueError()
        ids=set();decoded={}
        for key,f in files.items():
            if not ID.fullmatch(key) or not re.fullmatch(r'TEST_[A-Za-z0-9_-]{1,70}\.pdf',f['name']):raise ValueError()
            blob=base64.b64decode(f['base64'],validate=True)
            if not blob.startswith(b'%PDF-') or len(blob)>MAX_PDF or hashlib.sha256(blob).hexdigest()!=f['sha256']:raise ValueError()
            decoded[key]=(f['name'],blob)
        for r in records:
            if set(r)!={'id','kind','number','customer','status','total','balance','details','file_ids'}:raise ValueError()
            if not ID.fullmatch(r['id']) or r['id'] in ids:raise ValueError()
            ids.add(r['id'])
            if r['kind'] not in ('invoice','quote','payment','customer','credit'):raise ValueError()
            for k in ('number','customer','status','total','balance','details'):
                if not isinstance(r[k],str) or len(r[k])>4000:raise ValueError()
            for k in ('total','balance'):
                if r[k] and (not Decimal(r[k]).is_finite() or abs(Decimal(r[k]))>Decimal('1000000000')):raise ValueError()
            if not isinstance(r['file_ids'],list) or any(x not in decoded for x in r['file_ids']):raise ValueError()
        if set(decoded)!={x for r in records for x in r['file_ids']}:raise ValueError()
        return records,decoded
    except (ValueError,KeyError,TypeError,InvalidOperation,AttributeError):
        raise PilotError('HISTORY_ARCHIVE_INVALID',503) from None

class Archive:
    def __init__(self,storage=None):
        self.storage=storage;self.lock=threading.Lock();self.loaded=None
    def load(self):
        with self.lock:
            if self.loaded is None:
                digest=os.environ.get('CU_HISTORY_ARCHIVE_SHA256','')
                if digest:
                    if not re.fullmatch('[a-f0-9]{64}',digest):raise PilotError('HISTORY_CONFIG_INVALID',503)
                    if self.storage is None:raise PilotError('STORAGE_NOT_CONFIGURED',503)
                    self.storage.confirm_private_bucket()
                    from private_storage import BUCKET
                    raw=self.storage._call('GET','/object/authenticated/'+BUCKET+'/history089/'+digest+'.json',max_download=MAX_ARCHIVE)
                    if hashlib.sha256(raw).hexdigest()!=digest:raise PilotError('HISTORY_CHECKSUM_FAILED',503)
                else:
                    raw=(ROOT/'history_fixture.json').read_bytes()
                self.loaded=validate(raw)
            return self.loaded
    def listing(self,query):
        try:
            p=parse_qs(query,keep_blank_values=True,strict_parsing=False)
            if set(p)-{'q','kind','positive','page'} or any(len(v)!=1 for v in p.values()):raise ValueError()
            q=p.get('q',[''])[0].strip().casefold()
            kind=p.get('kind',[''])[0];positive=p.get('positive',['0'])[0]
            page=int(p.get('page',['1'])[0])
            if len(q)>200 or page<1 or page>100000 or positive not in ('0','1') or kind not in ('','invoice','quote','payment','customer','credit'):raise ValueError()
        except ValueError:raise PilotError('HISTORY_QUERY_INVALID',400) from None
        rows,_=self.load()
        selected=[r for r in rows if (not kind or r['kind']==kind) and
                  (positive=='0' or r['kind']=='invoice' and Decimal(r['balance'] or '0')>0) and
                  (not q or q in ' '.join(r[k] for k in ('number','customer','status','details')).casefold())]
        result=[{k:v for k,v in r.items() if k not in ('details','file_ids')} for r in selected[(page-1)*50:page*50]]
        return {'data':result,'total':len(selected),'page':page,'page_size':50,'data_class':'fictional'}
    def detail(self,ident):
        rows,files=self.load()
        r=next((r for r in rows if r['id']==ident),None)
        if r is None:raise PilotError('NOT_FOUND',404)
        out={k:v for k,v in r.items() if k!='file_ids'}
        out['attachments']=[{'name':files[k][0],'url':'/api/history/files/'+k} for k in r['file_ids']]
        return out
    def pdf(self,ident):
        _,files=self.load()
        if ident not in files:raise PilotError('NOT_FOUND',404)
        return files[ident]
