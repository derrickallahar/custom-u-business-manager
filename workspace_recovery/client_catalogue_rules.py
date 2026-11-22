"""108 immutable catalogue snapshots and their retained image references."""
from recover_crm import uid,date,require
from catalogue_rules import chain
from catalogue_data import text,items_valid,snapshot_assets
FIELDS={'id','customer_id','customer_name','title','intro','items','pdf_version','active','version','created_at','updated_at'}
def record(r):
    require(isinstance(r,dict) and set(r)==FIELDS);uid(r['id']);uid(r['customer_id']);text(r['customer_name'],160,True);text(r['title'],120,True);text(r['intro'],600);items_valid(r['items'])
    require(r['pdf_version']=='108' and type(r['active']) is bool and type(r['version']) is int and 1<=r['version']<=999999999);require(date(r['updated_at'])>=date(r['created_at']))
def assets_for(r,obj):return snapshot_assets(r,obj)

def validate_client_catalogues(obj):
    require(isinstance(obj['client_catalogues'],list) and len(obj['client_catalogues'])<=500 and isinstance(obj['client_catalogue_audit'],list) and len(obj['client_catalogue_audit'])<=5000)
    records={}
    for r in obj['client_catalogues']:
        record(r);require(r['id'] not in records);assets_for(r,obj);records[r['id']]=r
    chain(obj['client_catalogue_audit'],records,'catalogue_id',record,immutable=True)
