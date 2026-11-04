"""ShopVox customer CSV mapping. Pure parsing; no network or database writes."""
import csv
import hashlib
import io
import json
import re
import uuid
from collections import defaultdict, Counter

MAX_CSV_BYTES = 512 * 1024
MAX_ROWS = 1000
HEADERS = ['Company Name', 'Enabled', 'Sales Reps', 'Tax', 'Tags', 'Pricing Level',
           'Created At', 'Created By', 'Updated At', 'Updated By', 'Website', 'Street',
           'Street 1', 'City', 'State', 'ZIP', 'Suburb', 'Country', 'Label',
           'Primary Contact', 'Primary Contact Email', 'Primary Contact Phone',
           'Contact Title', 'Legal Name', 'Tax Exempt Code', 'Address Type',
           'Attention To', 'Secondary Address Type', 'Secondary Attention To',
           'Secondary Street', 'Secondary Street 1', 'Secondary Suburb',
           'Secondary City', 'Secondary State', 'Secondary ZIP', 'Secondary Country',
           'Local File Path', 'Background Info', 'VAT Number', 'Discount',
           'Primary Phone Ext.', 'Special Notes', 'Other Info', 'Terms', 'Credit Limit',
           'Contact First Name', 'Contact Last Name']
MAPPED = {'Company Name', 'Enabled', 'Street', 'Street 1', 'City', 'State', 'ZIP',
          'Suburb', 'Country', 'Primary Contact', 'Primary Contact Email',
          'Primary Contact Phone', 'Contact Title', 'VAT Number'}
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def name_key(value):
    return re.sub('[^a-z0-9]', '', value.lower())


def pair_key(data):
    email = data.get('email', '').strip().lower()
    phone = re.sub('[^0-9]', '', data.get('phone', ''))
    if len(phone) == 11 and phone.startswith('1'):
        phone = phone[1:]
    return email + '|' + phone if email and len(phone) >= 7 else ''


def record_id(source, kind):
    # Stable row-content identities. UUID v4 encoding satisfies the 093 ID contract;
    # these IDs are content-derived, NOT random. A reordered CSV keeps its IDs.
    raw = json.dumps(source, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    digest = hashlib.sha256(('custom-u-shopvox-customer-095:' + kind + ':' + raw).encode()).digest()
    return str(uuid.UUID(bytes=digest[:16], version=4))


def parse_csv(text):
    if not isinstance(text, str) or not text or len(text.encode('utf-8')) > MAX_CSV_BYTES:
        raise ValueError('CSV_TOO_LARGE_OR_EMPTY')
    reader = csv.reader(io.StringIO(text.lstrip('\ufeff'), newline=''), strict=True)
    try:
        headers = next(reader)
        if len(headers) != len(HEADERS) or len(set(headers)) != len(headers) or set(headers) != set(HEADERS):
            raise ValueError('CUSTOMER_CSV_HEADERS_REQUIRED')
        sources = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(headers):
                raise ValueError('CSV_COLUMN_COUNT_INVALID')
            sources.append(dict(zip(headers, row)))
            if len(sources) > MAX_ROWS:
                raise ValueError('CSV_ROW_LIMIT_REACHED')
    except (csv.Error, StopIteration):
        raise ValueError('CSV_FORMAT_INVALID') from None
    if not sources:
        raise ValueError('CSV_TOO_LARGE_OR_EMPTY')
    rows = []
    for i, source in enumerate(sources, 2):
        s = {k: v.strip() for k, v in source.items()}
        customer = {'name': s['Company Name'], 'email': s['Primary Contact Email'],
                    'phone': s['Primary Contact Phone'], 'tax_id': s['VAT Number'],
                    'address': ', '.join(s[k] for k in ['Street', 'Street 1', 'Suburb', 'City', 'State', 'ZIP', 'Country'] if s[k])}
        contact = {'name': s['Primary Contact'], 'email': s['Primary Contact Email'],
                   'phone': s['Primary Contact Phone'], 'title': s['Contact Title']} if s['Primary Contact'] else None
        problems = []
        notes = []
        if s['Enabled'] != 'Yes':
            problems.append('Inactive in the export' if s['Enabled'] == 'No' else 'Unrecognized enabled status')
        if not name_key(customer['name']):
            problems.append('Customer name needs review')
        for kind, data in [('Customer', customer), ('Contact', contact)]:
            if not data:
                continue
            if not 1 <= len(data['name']) <= 160:
                problems.append(kind + ' name is missing or too long')
            for key, value in data.items():
                if len(value) > (500 if key == 'address' else 254) or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value):
                    problems.append(kind + ' ' + key + ' needs review')
            if data.get('email') and not EMAIL.fullmatch(data['email']):
                problems.append(kind + ' email needs review')
        for field, label in [('Primary Contact', 'primary contact'), ('Primary Contact Email', 'email'), ('Primary Contact Phone', 'phone'), ('Street', 'street address')]:
            if not s[field]:
                notes.append('No ' + label + ' in export')
        if any(source[k] != s[k] for k in MAPPED):
            notes.append('Leading/trailing spaces trimmed')
        rows.append({'row': i, 'id': record_id(source, 'customer'),
                     'contact_id': record_id(source, 'contact') if contact else None,
                     'customer': customer, 'contact': contact, 'problems': problems, 'notes': notes})
    for key, reason in [(lambda r: name_key(r['customer']['name']), 'Similar customer name in this CSV'),
                        (lambda r: pair_key(r['customer']), 'Same email and phone in this CSV')]:
        groups = defaultdict(list)
        for row in rows:
            value = key(row)
            if value:
                groups[value].append(row)
        for group in groups.values():
            if len(group) > 1:
                nums = ', '.join(str(r['row']) for r in group)
                for row in group:
                    row['problems'].append(reason + ' (rows ' + nums + ')')
    # Sharing only a phone or email can be legitimate; report it without merging.
    for field in ('email', 'phone'):
        groups = Counter(r['customer'][field].lower() for r in rows if r['customer'][field])
        for row in rows:
            if groups[row['customer'][field].lower()] > 1:
                row['notes'].append('Shares ' + field + ' with another CSV customer')
    retained = {k: sum(bool(s[k].strip()) for s in sources) for k in HEADERS if k not in MAPPED}
    return {'format': 'custom-u-customer-import-preview-095',
            'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'rows': rows, 'archive_only_fields': {k: n for k, n in retained.items() if n}}


def preview(parsed, existing):
    """Classify all source rows against a single CRM snapshot; never merge."""
    ids = {r['id']: r for r in existing}
    names, pairs = defaultdict(list), defaultdict(list)
    for record in existing:
        if record['kind'] == 'customer':
            names[name_key(record['data']['name'])].append(record['data']['name'])
            if pair_key(record['data']):
                pairs[pair_key(record['data'])].append(record['data']['name'])
    result = json.loads(json.dumps(parsed))
    payloads = []
    for row in result['rows']:
        previous = ids.get(row['id'])
        if previous:
            old_contact = ids.get(row['contact_id']) if row['contact_id'] else None
            complete = previous['kind'] == 'customer' and (not row['contact_id'] or (old_contact and old_contact['kind'] == 'contact' and old_contact['customer_id'] == row['id']))
            row['status'] = 'already_added' if complete else 'review'
            row['problems'] = ['Already added from this source row; existing edits will be kept'] if complete else ['Source identity conflict; needs review']
            continue
        matches = set(names.get(name_key(row['customer']['name']), [])) | set(pairs.get(pair_key(row['customer']), []))
        if matches:
            row['problems'].append('Possible match already in CRM: ' + ', '.join(sorted(matches)))
        if row['contact_id'] in ids:
            row['problems'].append('Contact identity already exists')
        row['status'] = 'review' if row['problems'] else 'ready'
        if row['status'] == 'ready':
            payloads.append({'op': 'save_customer', 'id': row['id'], 'version': 0, 'active': True, 'data': row['customer']})
            if row['contact']:
                payloads.append({'op': 'save_contact', 'id': row['contact_id'], 'customer_id': row['id'], 'version': 0, 'active': True, 'data': row['contact']})
    result['counts'] = {s: sum(r['status'] == s for r in result['rows']) for s in ('ready', 'review', 'already_added')}
    result['counts']['total'] = len(result['rows'])
    result['counts']['contacts_to_add'] = sum(p['op'] == 'save_contact' for p in payloads)
    return result, payloads
