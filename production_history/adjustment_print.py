"""Private, escaped credit notes and refund records from saved invoice details."""
from datetime import timezone
from quote_print import h,money,amount,lines_text,details
from payment_print import STYLE
from adjustment_rules import credit_record,refund_record
from payment_rules import METHODS,timestamp

def shell(inv,r,title,body):
    q=inv['quote_snapshot'];seller=q['seller_snapshot'];buyer={**q['customer_snapshot'],'address':inv['details']['billing_address'],'tax_id':inv['details']['billing_tax_id']}
    banner='TEST — PRACTICE ONLY · NOT A COMMERCIAL OR TAX DOCUMENT' if r['is_test'] else ''
    if r['status']=='draft':banner+=(' · ' if banner else '')+'DRAFT — NOT ISSUED'
    if r['status']=='reversed':banner+=(' · ' if banner else '')+'REVERSED — INVALID RECORD'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+h(r['number'])+'</title><style>'+STYLE+'</style></head><body><p class="print-help">Use your browser’s Print command to print or save as PDF. <a href="/credits?invoice='+h(inv['id'])+'">Back to credits and refunds</a></p><div class="page-stamp">'+h(r['number'])+(' · '+h(banner) if banner else '')+'</div><main class="sheet">'+('<p class="draft">'+h(banner)+'</p>' if banner else '')+'<div class="heading"><div><h1>'+h(seller['name'])+'</h1><p>'+details(seller,['address','email','phone','website'])+'</p><p>Supplier VAT ID: '+h(seller['tax_id'])+'</p></div><div class="right"><h2>'+h(title)+'</h2><h2>'+h(r['number'])+'</h2><p>Date: '+h(r['details'].get('credit_date',r['details'].get('refund_date','')))+'<br>Original invoice: '+h(inv['number'])+'<br>Original invoice date: '+h(inv['details']['invoice_date'])+'<br>Currency: BSD</p></div></div><div class="parties"><div><div class="label">Customer</div><strong>'+h(buyer['name'])+'</strong><p>'+details(buyer,['address','email','phone'])+'</p>'+('<p>Customer VAT ID: '+h(buyer['tax_id'])+'</p>' if buyer.get('tax_id') else '')+'</div><div><div class="label">Invoice title</div><p>'+h(q['data']['title'])+'</p></div></div>'+body+'<p class="footer">'+('Practice record only. No actual money is received, returned or payable.' if r['is_test'] else 'Keep this document with the original invoice and related payment records.')+'</p></main></body></html>'

def sums(values):return '<section class="totals">'+''.join('<div><span>'+h(name)+'</span><strong>'+money(value)+'</strong></div>' for name,value in values)+'</section>'

def render_credit(inv,r):
    credit_record(r,inv);d=r['details'];q=inv['quote_snapshot']['data'];rows=[]
    for x in d['lines']:
        l=q['lines'][x['line_index']];rows.append('<tr><td>'+str(x['line_index']+1)+'. '+lines_text(l['description'])+'</td><td class="num">'+amount(l['net_cents'])+'</td><td class="num">'+amount(x['net_cents'])+'</td><td class="num">'+h(inv['details']['tax_codes'][x['line_index']])+' · '+h(l['vat_rate'])+'%<br>'+amount(x['tax_cents'])+'</td><td class="num">'+amount(x['total_cents'])+'</td></tr>')
    body='<h2>Reduction in the invoiced value</h2><p>Original invoice: net '+money(q['subtotal_cents']-q['discount_cents'])+' + VAT '+money(q['tax_cents'])+' = '+money(q['total_cents'])+'.</p><table><colgroup><col style="width:36%"><col style="width:16%"><col style="width:16%"><col style="width:16%"><col style="width:16%"></colgroup><thead><tr><th>Original item</th><th class="num">Original net BSD</th><th class="num">Net reduction BSD</th><th class="num">VAT reduction BSD</th><th class="num">Credit total BSD</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+sums([('Previous credit notes',d['prior_credit_cents']),('This credit: net reduction',d['net_cents']),('This credit: VAT reduction',d['tax_cents']),('This credit: total reduction',d['total_cents']),('Corrected invoice value',q['total_cents']-d['prior_credit_cents']-d['total_cents'])])+'<section class="terms"><div class="label">Reason for adjustment</div><p>'+lines_text(d['reason'])+'</p></section><p class="footer">'+('This draft does not affect the balance. Review and finalise it to apply the credit.' if r['status']=='draft' else 'This credit reduces the original invoice value. It does not record a cash refund. Payments and refunds are recorded separately.')+' VAT is allocated from the original line amounts; cumulative rounding ensures a full credit returns the original VAT exactly. T: taxable · Z: zero-rated · E: exempt.</p>'
    return shell(inv,r,'VAT CREDIT NOTE' if inv['details']['document_type']=='vat_invoice' else 'CREDIT NOTE',body)

def render_refund(inv,r):
    refund_record(r,inv);d=r['details'];body=sums([('Refund recorded'+(' (TEST)' if r['is_test'] else ''),d['amount_cents'])])+'<section class="terms"><p>Method: '+h(METHODS[d['method']])+'<br>Reference: '+h(d['reference'] or 'Not supplied')+'</p><div class="label">Reason</div><p>'+lines_text(d['reason'])+'</p></section>'
    if r['status']=='reversed':body+='<section class="terms"><div class="label">Correction</div><p>Reversed on '+h(timestamp(r['reversed_at']).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+'. Reason: '+lines_text(r['reversal_reason'])+'</p></section>'
    body+='<p class="footer">This records a refund entered against the invoice shown. The application does not transfer money. A reversed record no longer counts towards refunds recorded; reversing it does not recover money from the customer.</p>'
    return shell(inv,r,'REFUND RECORD',body)
