"""Client-facing catalogue schema; supplier fields are never accepted."""
import re
from decimal import Decimal
from product_images import checked_bytes
UUID=re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
ITEM_FIELDS={'product_id','product_code','name','description','unit','unit_price','vat_rate','finish','placement','visual_kind','visual_id','visual_sha256'}
def require(ok):
    if not ok:raise ValueError('INVALID_CATALOGUE')
def text(value,limit,required=False):
    require(isinstance(value,str) and len(value)<=limit and (not required or bool(value.strip())) and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',value));return value
def uid(value):require(isinstance(value,str) and UUID.fullmatch(value))
def items_valid(items):
    require(isinstance(items,list) and 1<=len(items)<=12)
    for x in items:
        require(isinstance(x,dict) and set(x)==ITEM_FIELDS)
        uid(x['product_id']);uid(x['visual_id'])
        for k,n in [('product_code',40),('name',160),('description',400),('unit',20),('finish',160),('placement',160)]:text(x[k],n,k in ('product_code','name','unit'))
        require(isinstance(x['unit_price'],str) and re.fullmatch(r'(0|[1-9][0-9]{0,5})\.[0-9]{2}',x['unit_price']))
        require(isinstance(x['vat_rate'],str) and re.fullmatch(r'(0|[1-9][0-9]?|100)\.[0-9]{2}',x['vat_rate']) and Decimal(x['vat_rate'])<=100)
        require(x['visual_kind'] in ('image','mockup') and isinstance(x['visual_sha256'],str) and re.fullmatch('[a-f0-9]{64}',x['visual_sha256']))
    return items

def validate_document(d,assets):
    require(isinstance(d,dict) and {'customer_id','customer_name','title','intro','items'}<=set(d) and set(d)<={'id','customer_id','customer_name','title','intro','items','active','version','created_at','updated_at','pdf_version'})
    require(d.get('pdf_version','108')=='108');uid(d['customer_id']);text(d['customer_name'],160,True);text(d['title'],120,True);text(d['intro'],600);items_valid(d['items'])
    keys={x['visual_kind']+':'+x['visual_id'] for x in d['items']};require(isinstance(assets,dict) and set(assets)==keys)
    raw={key:checked_bytes(value) for key,value in assets.items()}
    for x in d['items']:require(assets[x['visual_kind']+':'+x['visual_id']]['sha256']==x['visual_sha256'])
    return raw

def snapshot_assets(d,obj):
    images={x['id']:x for x in obj['product_images']};mockups={x['id']:x for x in obj['mockups']};products={x['id'] for x in obj['products']};customers={x['id'] for x in obj['crm']['records'] if x['kind']=='customer'}
    require(d['customer_id'] in customers);assets={}
    for x in d['items']:
        require(x['product_id'] in products)
        source=(images if x['visual_kind']=='image' else mockups).get(x['visual_id']);require(source is not None and source['product_id']==x['product_id'])
        if x['visual_kind']=='mockup':require(source['customer_id']==d['customer_id'])
        assets[x['visual_kind']+':'+x['visual_id']]=source if x['visual_kind']=='image' else source['preview']
    validate_document(d,assets);return assets
