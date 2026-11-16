"""Private printable legacy balance register; never an invoice or tax credit note."""
from quote_print import h,money
STYLE='@page{size:letter;margin:15mm}body{font:14px Arial,sans-serif;color:#222}main{max-width:1000px;margin:auto}h1{color:#b72030}th,td{border-bottom:1px solid #ddd;text-align:left}.sheet{padding:15px}table{border-collapse:collapse}tr{break-inside:avoid}'
from legacy_rules import view

def printable(state,ident=None):
    d=view(state);rows=[r for r in d['rows'] if ident is None or r['id']==ident]
    if ident and not rows:raise ValueError('NOT_FOUND')
    mode='TEST — PRACTICE ONLY — NOT FOR CUSTOMER USE' if d['mode']=='test' else 'LIVE LEGACY BALANCES'
    out='<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Custom U · Legacy balance register</title><style>'+STYLE+'table{width:100%;font-size:11px}td,th{padding:7px;vertical-align:top}h2{break-before:page}h2:first-of-type{break-before:auto}.reversed{color:#777}</style></head><body><main class="sheet"><h1>Custom U · Legacy balance register</h1><p>'+h(mode)+'</p><p>Imported ShopVox balances and later records. This does not issue an invoice or tax credit note, move money, or apply a late fee.</p>'
    if d['book']:out+='<p>Opening balance date: '+h(d['book']['as_of'])+' · Review: '+h(d['book']['review_note'])+'</p>'
    for r in rows:
        out+='<h2>ShopVox '+h(r['number'])+' · '+h(r['customer_name'])+'</h2><p>Original total '+money(r['total_cents'])+' · Historical paid '+money(r['paid_cents'])+' · Historical credits '+money(r['credit_cents'])+'<br>Imported balance '+money(r['opening_cents'])+' · Subsequent payments '+money(r['subsequent_paid_cents'])+' · Subsequent credits '+money(r['subsequent_credit_cents'])+' · Remaining '+money(r['remaining_cents'])+'</p><table><thead><tr><th>Date</th><th>Record</th><th>Reference / reason</th><th>Amount</th><th>Status</th></tr></thead><tbody>'
        for e in r['activity']:
            out+='<tr'+(' class="reversed"' if e['reversed'] else '')+'><td>'+h(e['effective_date'])+'</td><td>'+h(e['kind'].capitalize())+'<br>'+h(e['id'])+'</td><td>'+h(e['reference'])+'<br>'+h(e['reason'])+'</td><td>'+money(e['amount_cents'])+'</td><td>'+('Reversed' if e['reversed'] else 'Recorded')+'</td></tr>'
        out+='</tbody></table>'
    return out+'</main></body></html>'
