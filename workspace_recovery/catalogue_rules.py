"""106 supplier and private-image audit chains, hashes and decoded dimensions."""
import re
from decimal import Decimal
from recover_crm import require,uid,date
from product_images import checked_bytes

LIMITS={'supplier':160,'url':2048,'sku':100,'cost':10,'currency':3,'colours':800,'sizes':800,'specifications':4000}
IMAGE_FIELDS={'id','product_id','filename','caption','source_url','sha256','size_bytes','width','height','active','version','created_at','updated_at'}

def https_url(value):
    require(isinstance(value,str) and len(value)<=2048)
    require(not value or re.fullmatch(r'https://[A-Za-z0-9][A-Za-z0-9.\-]*(?::443)?(?:/[^\s]*)?',value) is not None and not re.search(r'[\\<>"\x27]',value))

def source_record(r):
    require(isinstance(r,dict) and set(r)=={'id','data','version','created_at','updated_at'})
    uid(r['id']);require(type(r['version']) is int and 1<=r['version']<=999999999)
    require(date(r['updated_at'])>=date(r['created_at']))
    d=r['data'];require(isinstance(d,dict) and set(d)==set(LIMITS))
    for k,maxlen in LIMITS.items():
        v=d[k];require(isinstance(v,str) and v==v.strip(' ') and len(v)<=maxlen and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',v))
        if k!='specifications':require(not re.search(r'[\t\r\n]',v))
    https_url(d['url']);require(not d['currency'] or re.fullmatch('[A-Z]{3}',d['currency']))
    if d['cost']:require(bool(d['currency']) and re.fullmatch(r'(0|[1-9][0-9]{0,6})\.[0-9]{2}',d['cost']) and Decimal(d['cost'])<=1000000)

def image_record(r):
    require(isinstance(r,dict) and set(r)==IMAGE_FIELDS)
    uid(r['id']);uid(r['product_id']);require(type(r['active']) is bool and type(r['version']) is int and 1<=r['version']<=999999999)
    require(date(r['updated_at'])>=date(r['created_at']))
    require(isinstance(r['filename'],str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _().-]{0,150}\.webp',r['filename']))
    require(isinstance(r['caption'],str) and len(r['caption'])<=200 and not re.search(r'[\x00-\x1f\x7f]',r['caption']))
    https_url(r['source_url']);require(isinstance(r['sha256'],str) and re.fullmatch('[a-f0-9]{64}',r['sha256']))
    require(type(r['size_bytes']) is int and 12<=r['size_bytes']<=512000)
    require(all(type(r[k]) is int and 1<=r[k]<=1600 for k in ('width','height')))

def chain(audits,records,key,validator,immutable=False):
    require(isinstance(audits,list) and len(audits)<=100000)
    seen=set();latest={}
    for a in sorted(audits,key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        require(isinstance(a,dict) and set(a)=={'id',key,'actor_id','happened_at','before_record','after_record'})
        require(type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id']);date(a['happened_at'])
        ident=a[key];require(ident in records);before=a['before_record'];after=a['after_record'];require(before==latest.get(ident));validator(after);require(after['id']==ident)
        if before is None:require(after['version']==1 and (not immutable or after['active'] is True))
        else:
            require(after['version']==before['version']+1 and after['created_at']==before['created_at'] and date(after['updated_at'])>=date(before['updated_at']))
            if immutable:require(after['active']!=before['active'] and {k:v for k,v in after.items() if k not in ('active','version','updated_at')}=={k:v for k,v in before.items() if k not in ('active','version','updated_at')})
        latest[ident]=after
    require(latest==records)

def validate_catalogue(obj):
    require(all(isinstance(obj[k],list) for k in ('product_sources','product_source_audit','product_images','product_image_audit')))
    require(len(obj['product_sources'])<=5000 and len(obj['product_images'])<=5000)
    products={p['id'] for p in obj['products']};sources={};images={};counts={};total=0
    for r in obj['product_sources']:
        source_record(r);require(r['id'] in products and r['id'] not in sources);sources[r['id']]=r
    for r in obj['product_images']:
        require(isinstance(r,dict) and set(r)==IMAGE_FIELDS|{'content_base64'})
        metadata={k:v for k,v in r.items() if k!='content_base64'};image_record(metadata)
        require(r['product_id'] in products and r['id'] not in images);images[r['id']]=metadata
        counts[r['product_id']]=counts.get(r['product_id'],0)+1;require(counts[r['product_id']]<=50)
        total+=r['size_bytes'];require(total<=40000000);checked_bytes(r)
    chain(obj['product_source_audit'],sources,'product_id',source_record)
    chain(obj['product_image_audit'],images,'image_id',image_record,immutable=True)
