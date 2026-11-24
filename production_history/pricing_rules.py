"""Canonical catalogue parameter validation, including draft prices."""
import re


def matrix_valid(data, active=False):
    p=data.get('pricing')
    if not isinstance(p,dict) or set(p)!={'mode','minimum','options','axes','basis','quantity_axis'} or p['mode']!='matrix':return False
    def amount(v,maximum=1000000):
        return isinstance(v,str) and (v=='' or re.fullmatch(r'(0|[1-9][0-9]{0,6})\.[0-9]{2}',v) is not None and float(v)<=maximum)
    def label(v):return isinstance(v,str) and v==v.strip() and 1<=len(v)<=160 and not re.search(r'[\x00-\x1f\x7f]',v)
    if data.get('unit_price')!='' or not amount(data.get('vat_rate'),100) or not amount(p['minimum']):return False
    if p['basis'] not in ('each','run','quantity') or data.get('unit')!=('Run' if p['basis']=='run' else 'Each'):return False
    if type(p['quantity_axis']) is not int or p['quantity_axis']!=(0 if p['basis']=='quantity' else -1):return False
    if not isinstance(p['axes'],list) or not 1<=len(p['axes'])<=3:return False
    for a in p['axes']:
        if not isinstance(a,dict) or set(a)!={'label','values'} or not label(a['label']) or not isinstance(a['values'],list) or not 1<=len(a['values'])<=100:return False
        if not all(label(v) for v in a['values']) or len(set(a['values']))!=len(a['values']):return False
    if p['basis']=='quantity' and not all(re.fullmatch(r'[1-9][0-9]{0,6}',v) and int(v)<=1000000 for v in p['axes'][0]['values']):return False
    if not isinstance(p['options'],list) or not 1<=len(p['options'])<=300:return False
    seen=set()
    for o in p['options']:
        if not isinstance(o,dict) or set(o)!={'values','price'} or not isinstance(o['values'],list) or len(o['values'])!=len(p['axes']) or not amount(o['price']):return False
        if not all(isinstance(v,str) and v in a['values'] for v,a in zip(o['values'],p['axes'])):return False
        key=tuple(o['values'])
        if key in seen:return False
        seen.add(key)
    return not active or data['vat_rate']!='' and p['minimum']!='' and any(float(o['price'] or 0)>0 for o in p['options'])


def pricing_valid(data, active=False):
    p = data.get('pricing')
    if isinstance(p,dict) and p.get('mode')=='matrix':return matrix_valid(data,active)
    if not isinstance(p, dict) or set(p) != {'mode', 'minimum', 'options'}:
        return False
    if p['mode'] not in ('fixed', 'area', 'grid') or not isinstance(p['options'], list) or len(p['options']) > 50:
        return False
    def amount(v, maximum=1000000, blank=True):
        return isinstance(v, str) and (blank and v == '' or re.fullmatch(r'(0|[1-9][0-9]{0,6})\.[0-9]{2}', v) is not None and float(v) <= maximum)
    if not all(amount(v) for v in [data.get('unit_price'), p['minimum']]) or not amount(data.get('vat_rate'), 100):
        return False
    if p['mode'] == 'area' and data.get('unit') != 'Sqft' or p['mode'] == 'grid' and (data.get('unit') != 'Run' or data.get('unit_price') != ''):
        return False
    if p['mode'] != 'grid' and p['options']:
        return False
    labels = set()
    for o in p['options']:
        if not isinstance(o, dict) or set(o) != {'label', 'copies', 'price'}:
            return False
        label = o['label']
        if not isinstance(label, str) or label != label.strip() or not 1 <= len(label) <= 100 or re.search(r'[\x00-\x1f\x7f]', label) or label.lower() in labels:
            return False
        labels.add(label.lower())
        if not isinstance(o['copies'], str) or not re.fullmatch(r'[1-9][0-9]{0,6}', o['copies']) or int(o['copies']) > 1000000 or not amount(o['price']):
            return False
    if not active:
        return True
    if data['vat_rate'] == '' or p['minimum'] == '':
        return False
    if p['mode'] == 'grid':
        return any(o['price'] and float(o['price']) > 0 for o in p['options'])
    return bool(data['unit_price']) and float(data['unit_price']) > 0

