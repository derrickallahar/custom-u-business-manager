"""The user's four approved customer consolidations for one exact source export.

No customer values are embedded in deployment files. Values come from the uploaded
CSV; its checksum and the full approved plan digest are fixed, not caller options.
"""
import copy
import hashlib
import json
from customer_import import preview

SOURCE_SHA256 = '5bdd6ea1d4055c5988e0094892545773b6dc37f8219583c7f1359ecb0d846faf'
MERGES = {13: 276, 128: 282, 180: 488, 36: 442}
INACTIVE = 39
HELD = [6,13,36,39,46,97,111,121,128,136,180,206,211,228,276,282,302,
        304,343,353,376,400,418,439,442,444,453,471,488,494,518,523,569]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def make_plan(parsed):
    if parsed['source_sha256'] != SOURCE_SHA256:
        raise ValueError('APPROVED_SOURCE_REQUIRED')
    if len(parsed['rows']) != 598:
        raise ValueError('APPROVED_SOURCE_REQUIRED')
    by_row = {r['row']: r for r in parsed['rows']}
    initial, baseline = preview(parsed, [])
    if [r['row'] for r in initial['rows'] if r['status'] == 'review'] != HELD:
        raise ValueError('APPROVED_PLAN_CHANGED')
    items, coverage = [], []
    for n in HELD:
        if n == INACTIVE or n in MERGES:
            continue
        row = by_row[n]
        items.append({'op': 'save_customer', 'id': row['id'], 'version': 0,
                      'active': True, 'data': copy.deepcopy(row['customer'])})
        contact_ids = {}
        for source in [n] + sorted(k for k, v in MERGES.items() if v == n):
            member = by_row[source]
            contact_id = None
            if member['contact']:
                key = canonical(member['contact'])
                if key not in contact_ids:
                    contact_ids[key] = member['contact_id']
                    items.append({'op': 'save_contact', 'id': member['contact_id'],
                                  'customer_id': row['id'], 'version': 0, 'active': True,
                                  'data': copy.deepcopy(member['contact'])})
                contact_id = contact_ids[key]
            coverage.append({'row': source, 'source_id': member['id'],
                             'customer_id': row['id'], 'contact_id': contact_id})
    plan = {'format': 'custom-u-reviewed-customers-096', 'source_sha256': SOURCE_SHA256,
            'items': sorted(items, key=lambda i: (i['op'], i['id'])),
            'required_record_ids': sorted(p['id'] for p in baseline),
            'retired_customer_ids': sorted(by_row[n]['id'] for n in [INACTIVE] + list(MERGES)),
            'coverage': sorted(coverage, key=lambda c: c['row'])}
    return plan


def identities_complete(plan, existing):
    ids = {r['id']: r for r in existing}
    for item in plan['items']:
        r = ids.get(item['id'])
        if not r or r['kind'] != ('customer' if item['op'] == 'save_customer' else 'contact') or r.get('customer_id') != item.get('customer_id'):
            return False
    return not any(i in ids for i in plan['retired_customer_ids'])


def reviewed_preview(parsed, plan, state):
    report = copy.deepcopy(parsed)
    report['format'] = 'custom-u-reviewed-customer-preview-096'
    report['rows'] = [r for r in report['rows'] if r['row'] in HELD]
    complete = state['resolution_status'] == 'complete'
    for row in report['rows']:
        n = row['row']
        row['problems'] = []
        if n == INACTIVE:
            row['status'] = 'excluded'
            row['notes'].append('Inactive source copy stays in the archive; the active copy is row 439.')
        elif n in MERGES:
            row['status'] = 'combined'
            row['notes'].append('Approved as the same customer as row ' + str(MERGES[n]) + '; its contact details are included there.')
        else:
            row['status'] = 'already_added' if complete else 'ready'
            contacts = [i['data'] for i in plan['items'] if i.get('customer_id') == row['id']]
            row['extra_contacts'] = [c for c in contacts if c != row['contact']]
            aliases = sorted(k for k, v in MERGES.items() if v == n)
            if aliases:
                row['notes'].append('One customer for CSV rows ' + ', '.join(map(str, aliases + [n])) + '. All distinct contact details retained.')
            else:
                row['notes'].append('Kept as its own customer account despite shared contact details.')
    report['counts'] = {s: sum(r['status'] == s for r in report['rows']) for s in ('ready', 'review', 'already_added', 'combined', 'excluded')}
    report['counts'].update(total=33, contacts_to_add=0 if complete else 31)
    report['resolution'] = {'source_rows_reviewed': 33, 'customers': 28, 'contacts': 31,
                            'plan_sha256': hashlib.sha256(canonical(plan).encode()).hexdigest()}
    return report, [] if complete else plan['items']


def mark_completed_resolutions(report, parsed, existing):
    """The ordinary CSV preview must also recognize the completed consolidations."""
    if parsed['source_sha256'] != SOURCE_SHA256:
        return
    plan = make_plan(parsed)
    if not identities_complete(plan, existing):
        return
    approved, _ = reviewed_preview(parsed, plan, {'resolution_status': 'complete'})
    replacements = {r['row']: r for r in approved['rows']}
    report['rows'] = [replacements.get(r['row'], r) for r in report['rows']]
    report['counts'].update({s: sum(r['status'] == s for r in report['rows']) for s in ('ready', 'review', 'already_added', 'combined', 'excluded')})
