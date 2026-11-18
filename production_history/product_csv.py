"""Read-only ShopVox product mapping. Grid/formula prices are never inferred."""
import csv
import hashlib
import io
import re
import unicodedata
import uuid
from collections import Counter
from decimal import Decimal

REQUIRED = {'Product Name', 'Product Description', 'Category', 'Pricing Type',
            'Price ($)', 'Units', 'Active', 'Taxable', 'Formula'}
NAMESPACE = uuid.UUID('04da5398-d382-5aac-8c40-f60b45712542')
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
LIMITS = {'name': 160, 'description': 800, 'category': 80, 'unit': 20}


def name_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def money(value, maximum=1000000):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,7}(\.[0-9]{1,2})?', value.strip()):
        raise ValueError('INVALID_PRICE')
    amount = Decimal(value.strip())
    if amount > maximum:
        raise ValueError('INVALID_PRICE')
    return format(amount, '.2f')


def parse_csv(text):
    if not isinstance(text, str) or not text or len(text.encode('utf-8')) > 2*1024*1024:
        raise ValueError('CSV_SIZE_INVALID')
    if CONTROL.search(text):
        raise ValueError('CSV_CONTROL_CHARACTERS')
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff'), newline=''), strict=True)
        headers = reader.fieldnames
        if not headers or len(headers) != len(set(headers)) or not REQUIRED.issubset(headers):
            raise ValueError('CSV_HEADERS_INVALID')
        rows = []
        for n, source in enumerate(reader, 2):
            if len(rows) >= 1000:
                raise ValueError('CSV_ROW_LIMIT')
            if None in source or any(v is None for v in source.values()):
                raise ValueError('CSV_COLUMNS_INVALID')
            if not any(v.strip() for v in source.values()):
                continue
            rows.append({'row': n, 'source': source})
        if not rows:
            raise ValueError('CSV_EMPTY')
    except csv.Error:
        raise ValueError('CSV_FORMAT_INVALID') from None
    return {'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'rows': rows,
            'columns': headers}


def preview(parsed, existing):
    """Price-bearing, active Basic rows are candidates; VAT is always reviewed."""
    source_names = Counter(name_key(r['source']['Product Name']) for r in parsed['rows'])
    ids = {r['id']: r for r in existing}
    names = {name_key(r['data']['name']) for r in existing}
    codes = {r['data']['code'].casefold() for r in existing}
    result = []
    for row in parsed['rows']:
        s = row['source']
        name = s['Product Name'].strip()
        key = name_key(name)
        code = 'SVX-' + hashlib.sha256(key.encode()).hexdigest()[:24].upper()
        ident = str(uuid.uuid5(NAMESPACE, key))
        data = {'code': code, 'name': name, 'description': s['Product Description'].strip(),
                'category': s['Category'].strip(), 'unit': s['Units'].strip(),
                'unit_price': '', 'vat_rate': '', 'finish': '', 'placement': ''}
        problems = []
        for field, limit in LIMITS.items():
            value = data[field]
            if len(value) > limit or (field != 'description' and re.search(r'[\t\r\n]', value)):
                problems.append('Invalid or overlong ' + field + '; review the source.')
        if not name or not data['unit']:
            problems.append('Product name and selling unit are required.')
        if source_names[key] > 1:
            problems.append('Duplicate product name in this export; choose the correct record first.')
        if s['Active'].strip() != 'Yes':
            problems.append('Inactive or unrecognised active status; left out of the active catalogue.')
        if s['Pricing Type'].strip() != 'Basic' or s['Formula'].strip():
            problems.append('Grid or formula pricing needs its price table or a reviewed replacement unit price.')
        try:
            data['unit_price'] = money(s['Price ($)'])
            if Decimal(data['unit_price']) <= 0:
                problems.append('No positive selling price in this export.')
        except ValueError:
            problems.append('Selling price is missing or invalid.')
        if s['Taxable'].strip() not in ('Yes', 'No'):
            problems.append('Unrecognised Taxable value; review the source.')
        status = 'review' if problems else 'candidate'
        if ident in ids and ids[ident]['data']['code'].casefold() == code.casefold():
            status = 'already_added'
            problems = ['Already imported. Existing edits and active status will be kept.']
        elif ident in ids or code.casefold() in codes or key in names:
            status = 'existing'
            problems = ['An existing catalogue product has this name or code; it will not be overwritten.']
        result.append({'row': row['row'], 'id': ident, 'data': data, 'status': status,
                       'problems': problems, 'pricing_type': s['Pricing Type'],
                       'source_price': s['Price ($)'], 'source_taxable': s['Taxable'],
                       'source_active': s['Active'], 'source_formula': s['Formula'],
                       'source_template': s.get('Pricing Template', ''), 'source': dict(s)})
    counts = dict(Counter(r['status'] for r in result))
    for key in ('candidate', 'review', 'existing', 'already_added'):
        counts.setdefault(key, 0)
    counts['total'] = len(result)
    return {'source_sha256': parsed['sha256'], 'counts': counts, 'rows': result,
            'note': 'Preview only. Prices must be confirmed as BSD before VAT; choose VAT for every selected row. No images, grids, formulas or inventory quantities are imported.'}
