"""Canonical catalogue parameter validation, including draft prices."""
import re


def pricing_valid(data, active=False):
    p = data.get('pricing')
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

