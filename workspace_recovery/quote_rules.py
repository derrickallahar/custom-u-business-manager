"""Exact decimal quote arithmetic and snapshot checks; no network or side effects."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re

LINE_FIELDS={'description','finish','placement','unit','quantity','unit_price','discount_percent','vat_rate'}
QUOTE_FIELDS={'title','quote_date','valid_until','lines','terms','notes','deposit_percent','currency'}
PROFILE_FIELDS={'name','address','email','phone','tax_id','website','quote_terms','default_vat_rate','default_deposit_percent','validity_days','currency'}

def need(ok):
    if not ok: raise ValueError('INVALID_QUOTE_DATA')

def text(v,limit,multi=False,required=False):
    need(isinstance(v,str) and len(v)<=limit and not any((ord(c)<32 or ord(c)==127) and not (multi and c=='\n') for c in v))
    v=v.strip(' ');need(not required or bool(v));return v

def decimal(v,places,maximum,positive=False):
    need(isinstance(v,str) and re.fullmatch(r'[0-9]{1,7}(?:\.[0-9]{1,'+str(places)+r'})?',v) is not None)
    d=Decimal(v);need(d<=maximum and (d>0 if positive else d>=0));return d

def rounded(v):return int(v.quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def normalize_quote(d):
    need(isinstance(d,dict) and set(d)==QUOTE_FIELDS and d['currency']=='BSD')
    result={k:text(d[k],160 if k=='title' else 2000,k!='title',k=='title') for k in ('title','terms','notes')}
    for k in ('quote_date','valid_until'):
        need(isinstance(d[k],str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}',d[k]) is not None)
        date.fromisoformat(d[k]);result[k]=d[k]
    need(0<=(date.fromisoformat(d['valid_until'])-date.fromisoformat(d['quote_date'])).days<=366)
    dep=decimal(d['deposit_percent'],2,100)
    need(isinstance(d['lines'],list) and 1<=len(d['lines'])<=100)
    lines=[];subtotal=discounts=taxes=0
    for raw in d['lines']:
        need(isinstance(raw,dict) and set(raw)==LINE_FIELDS)
        l={k:text(raw[k],1000 if k=='description' else 20 if k=='unit' else 160,k=='description',k in ('description','unit')) for k in ('description','finish','placement','unit')}
        qty=decimal(raw['quantity'],3,1000000,True);price=decimal(raw['unit_price'],2,1000000)
        discount=decimal(raw['discount_percent'],2,100);vat=decimal(raw['vat_rate'],2,100)
        gross=rounded(qty*price*100);disc=rounded(Decimal(gross)*discount/100);net=gross-disc;tax=rounded(Decimal(net)*vat/100)
        l.update(quantity=f'{qty:.3f}',unit_price=f'{price:.2f}',discount_percent=f'{discount:.2f}',vat_rate=f'{vat:.2f}',gross_cents=gross,discount_cents=disc,net_cents=net,tax_cents=tax,total_cents=net+tax)
        subtotal+=gross;discounts+=disc;taxes+=tax;need(subtotal+taxes<=100000000000);lines.append(l)
    total=subtotal-discounts+taxes
    result.update(currency='BSD',lines=lines,deposit_percent=f'{dep:.2f}',subtotal_cents=subtotal,discount_cents=discounts,tax_cents=taxes,total_cents=total,deposit_cents=rounded(Decimal(total)*dep/100))
    return result

def quote_input(d):
    return {k:[{f:l[f] for f in LINE_FIELDS} for l in d[k]] if k=='lines' else d[k] for k in QUOTE_FIELDS}

def validate_saved_quote(d):
    need(normalize_quote(quote_input(d))==d)

def normalize_profile(d):
    need(isinstance(d,dict) and set(d)==PROFILE_FIELDS)
    out={k:text(d[k],2000 if k=='quote_terms' else 500 if k=='address' else 254,k in ('quote_terms','address'),k in ('name','address')) for k in ('name','address','email','phone','tax_id','website','quote_terms','currency')}
    need(len(out['name'])<=160 and out['currency']=='BSD' and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',out['email']) is not None)
    for k in ('default_vat_rate','default_deposit_percent'):out[k]=f'{decimal(d[k],2,100):.2f}'
    need(type(d['validity_days']) is int and 0<=d['validity_days']<=366);out['validity_days']=d['validity_days']
    return out
