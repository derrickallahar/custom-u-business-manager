"""Validate saved invoice revisions and their retained source quote."""
from datetime import date
from decimal import Decimal
import re
from quote_rules import need,text,validate_saved_quote,normalize_profile
FIELDS={'invoice_date','due_date','supply_date','document_type','billing_address','billing_tax_id','notes','terms','tax_codes'}

def normalize_details(d,q):
    need(isinstance(d,dict) and set(d)==FIELDS)
    need(d['document_type'] in ('vat_invoice','vat_sales_receipt'))
    out=dict(d)
    for k in ('invoice_date','due_date','supply_date'):
        need(isinstance(d[k],str))
        if k=='supply_date' and d[k]=='':continue
        need(re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}',d[k]) is not None);date.fromisoformat(d[k])
    starts=date.fromisoformat(d['invoice_date']);due=date.fromisoformat(d['due_date'])
    need(0<=(due-starts).days<=366)
    need(not d['supply_date'] or date.fromisoformat(d['supply_date'])<=starts)
    for k in ('billing_address','billing_tax_id','notes','terms'):out[k]=text(d[k],500 if k=='billing_address' else 100 if k=='billing_tax_id' else 2000,k!='billing_tax_id')
    need(isinstance(d['tax_codes'],list) and len(d['tax_codes'])==len(q['lines']))
    for l,c in zip(q['lines'],d['tax_codes']):
        need(c in ('','T','Z','E') and ((Decimal(l['vat_rate'])>0)==(c=='T')))
    return out

def validate_invoice_document(r):
    q=r['quote_snapshot'];validate_saved_quote(q['data'])
    if r['quote_id'] is None:
        need(r['quote_version'] is None and set(q)=={'source','customer_id','contact_id','customer_snapshot','customer_version','contact_snapshot','contact_version','seller_snapshot','seller_version','data'} and q['source']=='direct')
        need(isinstance(q['customer_id'],str) and re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',q['customer_id']) is not None)
        need(type(q['customer_version']) is int and q['customer_version']>0 and type(q['seller_version']) is int and q['seller_version']>0)
        need(isinstance(q['customer_snapshot'],dict) and isinstance(q['customer_snapshot'].get('name'),str))
        need(normalize_profile(q['seller_snapshot'])==q['seller_snapshot'])
        if q['contact_id'] is None:need(q['contact_snapshot'] is None and q['contact_version'] is None)
        else:need(isinstance(q['contact_id'],str) and re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',q['contact_id']) is not None and type(q['contact_version']) is int and q['contact_version']>0 and isinstance(q['contact_snapshot'],dict))
        need(q['data']['quote_date']==r['details']['invoice_date'] and q['data']['valid_until']==r['details']['due_date'] and q['data']['deposit_percent']=='0.00')
        need(q['data']['terms']==r['details']['terms'] and q['data']['notes']==r['details']['notes'])
    else:
        need(q['status'] in ('draft','issued') and r['quote_id']==q['id'] and r['quote_version']==q['version'])
        if 'original_quote_data' in q:validate_saved_quote(q['original_quote_data'])
    need(normalize_details(r['details'],q['data'])==r['details']);need(type(r['is_test']) is bool and r['status'] in ('draft','issued'))
    if r['status']=='issued':
        need(bool(q['seller_snapshot']['tax_id'].strip()) and '' not in r['details']['tax_codes'])
        if r['details']['document_type']=='vat_invoice':need(bool(r['details']['billing_address']) and bool(r['details']['billing_tax_id']))
