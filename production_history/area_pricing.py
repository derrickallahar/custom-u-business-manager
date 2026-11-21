"""Reviewed vinyl area pricing. Calculation only; no writes or email requests."""
import re

PRODUCT_ID = 'cc076f06-50f4-5b77-821f-f6ea9a329d76'
PRODUCT_CODE = 'SVX-890F38A1E26E9BF55E63C59F'
PRODUCT_NAME = 'Digitally Printed Permanent Adhesive Vinyl'
PERFORATED_ID = 'aa9cc9d2-4f68-5ae4-b576-da4f4748491d'
PRODUCTS = {
    PRODUCT_ID: {'code': PRODUCT_CODE, 'name': PRODUCT_NAME,
                 'finishes': ('', 'Matte', 'Gloss'), 'fixed_finish': ''},
    PERFORATED_ID: {'code': 'SVX-C97524326A513F6F6E88CDFE', 'name': 'Perforated Window Vinyl',
                    'finishes': ('', 'Optically clear'), 'fixed_finish': 'Optically clear lamination'},
}
FIELDS = {'product_id', 'width', 'height', 'dimension_unit', 'pieces', 'finish'}


def selected_product(body):
    if (not isinstance(body, dict) or set(body) != FIELDS or
            not isinstance(body['product_id'], str) or body['product_id'] not in PRODUCTS):
        raise ValueError('INVALID_AREA_REQUEST')
    return body['product_id']


def scaled(raw, places, maximum, code):
    if not isinstance(raw, str) or not re.fullmatch(r'[0-9]{1,7}(\.[0-9]{1,'+str(places)+r'})?', raw.strip()):
        raise ValueError(code)
    whole, _, fraction = raw.strip().partition('.')
    result = int(whole)*10**places + int(fraction.ljust(places, '0'))
    if result > maximum*10**places:
        raise ValueError(code)
    return result


def decimal_text(value, places):
    text = str(value//10**places)+'.'+str(value % 10**places).zfill(places)
    return text.rstrip('0').rstrip('.')


def money(cents):
    return str(cents//100)+'.'+str(cents % 100).zfill(2)


def half_up(numerator, denominator):
    return (2*numerator+denominator)//(2*denominator)


def calculate(body, product):
    ident = selected_product(body)
    spec = PRODUCTS[ident]
    if body['dimension_unit'] not in ('in', 'ft') or body['finish'] not in spec['finishes']:
        raise ValueError('INVALID_AREA_OPTIONS')
    width = scaled(body['width'], 3, 100000, 'INVALID_AREA_DIMENSIONS')
    height = scaled(body['height'], 3, 100000, 'INVALID_AREA_DIMENSIONS')
    if width <= 0 or height <= 0:
        raise ValueError('INVALID_AREA_DIMENSIONS')
    if not isinstance(body['pieces'], str) or not re.fullmatch(r'[0-9]{1,7}', body['pieces'].strip()):
        raise ValueError('INVALID_AREA_QUANTITY')
    pieces = int(body['pieces'])
    if not 1 <= pieces <= 1000000:
        raise ValueError('INVALID_AREA_QUANTITY')
    if not isinstance(product, dict) or not isinstance(product.get('data'), dict):
        raise ValueError('AREA_PRODUCT_UNAVAILABLE')
    d = product['data']
    if 'pricing' in d:
        raise ValueError('AREA_PRODUCT_UNAVAILABLE')
    if (product.get('id') != ident or product.get('active') is not True or
            type(product.get('version')) is not int or product['version'] < 1 or
            d.get('code') != spec['code'] or d.get('name') != spec['name'] or d.get('unit') != 'Sqft'):
        raise ValueError('AREA_PRODUCT_UNAVAILABLE')
    if spec['fixed_finish'] and d.get('finish', '') not in ('', spec['fixed_finish']):
        raise ValueError('AREA_PRODUCT_UNAVAILABLE')
    rate = scaled(d.get('unit_price'), 2, 1000000, 'AREA_PRODUCT_UNAVAILABLE')
    vat = scaled(d.get('vat_rate'), 2, 100, 'AREA_PRODUCT_UNAVAILABLE')
    if rate <= 0:
        raise ValueError('AREA_PRODUCT_UNAVAILABLE')
    # Exact rational area: dimensions in thousandths, multiplied by all pieces.
    # Round only the complete line amount, then VAT. Never round each tiny piece.
    area_n = width*height*pieces
    area_d = 1000000*(144 if body['dimension_unit'] == 'in' else 1)
    net = half_up(area_n*rate, area_d)
    if net <= 0:
        raise ValueError('AREA_AMOUNT_BELOW_ONE_CENT')
    if net > 100000000:
        raise ValueError('AREA_AMOUNT_TOO_LARGE')
    tax = half_up(net*vat, 10000)
    area_micro = half_up(area_n*1000000, area_d)
    area_text = decimal_text(area_micro, 6) if area_micro else '<0.000001'
    approximate = area_n*1000000 != area_micro*area_d
    w, h = decimal_text(width, 3), decimal_text(height, 3)
    unit_label = 'inches' if body['dimension_unit'] == 'in' else 'feet'
    area_label = ('approximately ' if approximate else '')+area_text+' sq ft'
    description = '\n'.join(x for x in [d['name'], d.get('description', ''),
        f'Size: {w} × {h} {unit_label}; quantity: {pieces} '+('piece' if pieces == 1 else 'pieces')+'.',
        f'Total area: {area_label}; rate: BSD {money(rate)}/sq ft.'] if x)
    finish = spec['fixed_finish'] or ' · '.join(x for x in [d.get('finish', ''), body['finish']+' UV lamination' if body['finish'] else ''] if x)
    if len(description) > 1000 or len(finish) > 160:
        raise ValueError('AREA_DESCRIPTION_TOO_LONG')
    line = {'description': description, 'finish': finish, 'placement': d.get('placement', ''),
            'quantity': '1', 'unit': 'Job', 'unit_price': money(net), 'discount_percent': '0', 'vat_rate': money(vat)}
    return {'product_id': ident, 'product_version': product['version'],
            'inputs': {**body, 'width': w, 'height': h, 'pieces': str(pieces),
                       'finish': 'Optically clear' if spec['fixed_finish'] else body['finish']},
            'area_sqft': area_text, 'area_approximate': approximate, 'rate': money(rate),
            'net_cents': net, 'vat_cents': tax, 'total_cents': net+tax, 'line': line}
