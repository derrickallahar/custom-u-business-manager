"""Resolve documents by immutable audited revision, never by the latest price."""
from quote_rules import need

def invoice_versions(obj):
    versions={(r['id'],r['version']):r for r in obj['invoices']}
    for a in obj.get('invoice_audit',[]):
        for key in ('before_record','after_record'):
            r=a.get(key)
            if r is not None:
                k=(r['id'],r['version'])
                need(k not in versions or versions[k]==r)
                versions[k]=r
    return versions

def linked_invoice(record,versions):
    r=versions.get((record['invoice_id'],record['invoice_version']))
    need(r is not None)
    return r


def check_financial_history(obj,records):
    versions=invoice_versions(obj)
    for record in records:
        origin=linked_invoice(record,versions)
        def signature(i):
            lines=[{k:v for k,v in l.items() if k not in ('description','finish','placement')} for l in i['quote_snapshot']['data']['lines']]
            return lines,i['details']['tax_codes'],i['details']['invoice_date']
        for (iid,version),i in versions.items():
            if iid==origin['id'] and version>=origin['version']:need(signature(i)==signature(origin))
