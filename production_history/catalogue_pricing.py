"""Editable fixed, square-foot and exact-variant pricing. No financial writes."""
import re
from area_pricing import scaled, half_up, money, decimal_text


from pricing_rules import pricing_valid


def calculate(body, product):
    if not isinstance(body, dict) or set(body) != {'product_id', 'version', 'width', 'height', 'dimension_unit', 'pieces', 'option'}:
        raise ValueError('INVALID_PRICING_REQUEST')
    d = (product or {}).get('data', {})
    if not product or type(product.get('version')) is not int or product['version']<1 or product.get('id') != body['product_id'] or product.get('active') is not True or not pricing_valid(d, True):
        raise ValueError('PRICING_UNAVAILABLE')
    if type(body['version']) is not int or body['version'] != product['version']:
        raise ValueError('PRICING_CHANGED')
    p = d['pricing']
    pieces = body['pieces']
    if not isinstance(pieces, str) or not re.fullmatch(r'[1-9][0-9]{0,6}', pieces) or int(pieces) > 1000000:
        raise ValueError('INVALID_PRICING_QUANTITY')
    count = int(pieces)
    if not all(isinstance(body[k], str) for k in ('width', 'height', 'dimension_unit', 'option')):
        raise ValueError('INVALID_PRICING_REQUEST')
    if p['mode'] == 'area':
        if body['dimension_unit'] not in ('in', 'ft') or body['option']:
            raise ValueError('INVALID_PRICING_REQUEST')
        w = scaled(body['width'], 3, 100000, 'INVALID_PRICING_DIMENSIONS')
        h = scaled(body['height'], 3, 100000, 'INVALID_PRICING_DIMENSIONS')
        if not w or not h:
            raise ValueError('INVALID_PRICING_DIMENSIONS')
        rate = scaled(d['unit_price'], 2, 1000000, 'PRICING_UNAVAILABLE')
        net = half_up(w*h*count*rate, 1000000*(144 if body['dimension_unit'] == 'in' else 1))
        details = f"Size: {decimal_text(w, 3)} × {decimal_text(h, 3)} {'inches' if body['dimension_unit'] == 'in' else 'feet'}; quantity: {count} piece(s)."
    elif p['mode'] == 'grid':
        if body['width'] or body['height'] or body['dimension_unit']:
            raise ValueError('INVALID_PRICING_REQUEST')
        option = next((o for o in p['options'] if o['label'] == body['option']), None)
        if not option or not option['price'] or float(option['price']) <= 0:
            raise ValueError('PRICING_UNAVAILABLE')
        net = scaled(option['price'], 2, 1000000, 'PRICING_UNAVAILABLE')*count
        details = f"{option['label']} — {option['copies']} copies per run; {count} run(s)."
    else:
        if body['width'] or body['height'] or body['dimension_unit'] or body['option']:
            raise ValueError('INVALID_PRICING_REQUEST')
        net = scaled(d['unit_price'], 2, 1000000, 'PRICING_UNAVAILABLE')*count
        details = f"Quantity: {count} {d['unit']}."
    net = max(net, scaled(p['minimum'], 2, 1000000, 'PRICING_UNAVAILABLE'))
    if not 1 <= net <= 100000000:
        raise ValueError('INVALID_PRICING_TOTAL')
    vat = scaled(d['vat_rate'], 2, 100, 'PRICING_UNAVAILABLE')
    tax = half_up(net*vat, 10000)
    description = '\n'.join(x for x in [d['name'], d['description'], details] if x)
    if len(description) > 1000:
        raise ValueError('PRICING_DESCRIPTION_TOO_LONG')
    return {'product_id': product['id'], 'version': product['version'], 'net_cents': net, 'vat_cents': tax, 'total_cents': net+tax,
            'line': {'description': description, 'quantity': '1', 'unit': 'Job', 'unit_price': money(net), 'discount_percent': '0', 'vat_rate': d['vat_rate'], 'finish': d['finish'], 'placement': d['placement']}}
