"""107 saved logo/preview bytes and immutable mockup audit chains."""
import re
from recover_crm import require,uid,date
from catalogue_rules import chain
from product_images import checked_bytes
from mockup_render import configuration

FIELDS={'id','product_id','image_id','customer_id','title','customer_name','product_name','product_code','base_sha256','config','logo','preview','active','version','created_at','updated_at'}
def metadata(record):return {**record,**{k:{a:b for a,b in record[k].items() if a!='content_base64'} for k in ('logo','preview')}}
def record_meta(r):
    require(isinstance(r,dict) and set(r)==FIELDS)
    for k in ('id','product_id','image_id','customer_id'):uid(r[k])
    require(type(r['active']) is bool and type(r['version']) is int and 1<=r['version']<=999999999)
    require(date(r['updated_at'])>=date(r['created_at']))
    for k in ('title','customer_name','product_name','product_code'):
        require(isinstance(r[k],str) and 1<=len(r[k])<=200 and not re.search(r'[\x00-\x1f\x7f]',r[k]))
    require(len(r['title'])<=160 and re.fullmatch('[a-f0-9]{64}',r['base_sha256']) is not None)
    configuration(r['config'])
    for k in ('logo','preview'):
        d=r[k];require(isinstance(d,dict) and set(d)=={'sha256','width','height','size_bytes'})
        require(isinstance(d['sha256'],str) and re.fullmatch('[a-f0-9]{64}',d['sha256']) is not None)
        require(type(d['size_bytes']) is int and 12<=d['size_bytes']<=512000)
        require(all(type(d[a]) is int and 1<=d[a]<=1600 for a in ('width','height')))
def validate_mockups(obj):
    require(isinstance(obj['mockups'],list) and len(obj['mockups'])<=500 and isinstance(obj['mockup_audit'],list) and len(obj['mockup_audit'])<=10000)
    products={r['id'] for r in obj['products']};images={r['id']:r for r in obj['product_images']}
    customers={r['id'] for r in obj['crm']['records'] if r['kind']=='customer'}
    records={};total=0
    for r in obj['mockups']:
        require(isinstance(r,dict) and set(r)==FIELDS)
        for k in ('logo','preview'):
            require(isinstance(r[k],dict) and set(r[k])=={'sha256','width','height','size_bytes','content_base64'});checked_bytes(r[k]);total+=r[k]['size_bytes']
        m=metadata(r);record_meta(m);require(r['id'] not in records and r['product_id'] in products and r['customer_id'] in customers and r['image_id'] in images)
        image=images[r['image_id']];require(image['product_id']==r['product_id'] and image['sha256']==r['base_sha256']);records[r['id']]=m
    require(total<=10000000);chain(obj['mockup_audit'],records,'mockup_id',record_meta,immutable=True)
