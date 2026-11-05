"""Invoice metadata validation; prices are immutable saved quote values."""
from datetime import date
from decimal import Decimal
import re
from quote_rules import need,text,validate_saved_quote
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
    q=r['quote_snapshot'];validate_saved_quote(q['data']);need(q['status']=='issued' and r['quote_id']==q['id'] and r['quote_version']==q['version'])
    need(normalize_details(r['details'],q['data'])==r['details']);need(type(r['is_test']) is bool and r['status'] in ('draft','issued'))
    if r['status']=='issued':
        need(bool(q['seller_snapshot']['tax_id'].strip()) and '' not in r['details']['tax_codes'])
        if r['details']['document_type']=='vat_invoice':need(bool(r['details']['billing_address']) and bool(r['details']['billing_tax_id']))
