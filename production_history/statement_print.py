"""Escaped current account statements and receivables print views."""
from quote_print import h,money,amount,details
from payment_print import STYLE
from statement_rules import BUCKETS
LABELS=('Not overdue','1–30 days','31–60 days','61–90 days','91+ days')
KINDS={'invoice':'Invoice','credit':'Credit note','payment':'Payment','refund':'Refund'}
def signed(n):return ('−' if n<0 else '')+amount(abs(n))
def summary(t):
    items=[('Original invoices',t['total_cents']),('Credit notes',t['credit_cents']),('Payments recorded',t['payment_cents']),('Refunds recorded',t['refund_cents']),('Amount owed',t['balance_cents']),('Refunds due',t['refund_due_cents'])]
    return '<div class="figures">'+''.join('<div><span>'+h(k)+'</span><strong>'+money(v)+'</strong></div>' for k,v in items)+'</div>'
def ageing(t):return '<h3>Amount owed by days past due</h3><table class="age"><thead><tr>'+''.join('<th class="num">'+h(k)+'</th>' for k in LABELS)+'</tr></thead><tbody><tr>'+''.join('<td class="num">'+amount(t[k])+'</td>' for k in BUCKETS)+'</tr></tbody></table><p class="small">All amounts in BSD. Due today is not overdue. Only unpaid amounts are aged; refunds due are shown separately.</p>'
def shell(d,title,body,landscape=False):
    seller=d.get('seller') or {'name':'Custom U'};mode='TEST — PRACTICE ONLY · NOT FOR CUSTOMER USE' if d['test_mode'] else 'LIVE'
    css=STYLE+' .figures{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.figures>div{padding:10px;background:#f5f6fa}.figures strong{display:block;font-size:17px;margin-top:5px}.small{font-size:11px;color:#606772}h3{margin:22px 0 8px}.age{margin:10px 0}.num{font-variant-numeric:tabular-nums}.statement tr.reversed{color:#777}.page-stamp{font-size:8px!important}@media print{.figures{break-inside:avoid}.figures strong{font-size:15px}'+(' @page{size:letter landscape;}' if landscape else '')+'}'
    if landscape:css+=' @page{size:letter landscape;}'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+h(title)+'</title><style>'+css+'</style></head><body><p class="print-help">Use Print to print or save as PDF. <a href="/statements">Back to statements</a></p><div class="page-stamp">'+h(title)+' · '+h(d['as_of'])+' · '+h(mode)+'</div><main class="sheet">'+('<p class="draft">'+h(mode)+'</p>' if d['test_mode'] else '')+'<div class="heading"><div><h1>'+h(seller.get('name','Custom U'))+'</h1><p>'+details(seller,['address','email','phone','website'])+'</p></div><div class="right"><h2>'+h(title)+'</h2><p>Current balances: '+h(d['as_of'])+' (Nassau)<br>Generated: '+h(d['generated_at'])+'<br>Currency: BSD</p></div></div>'+body+'<p class="footer">'+h(d['scope'])+'</p><p class="footer">Current account summary. Keep the original invoices, credit notes and payment/refund records. This report does not issue a tax document or record a payment.</p></main></body></html>'
def render_statement(d):
    buyer=d['customer'];body='<div class="parties"><div><div class="label">Customer</div><strong>'+h(buyer['name'])+'</strong><p>'+details(buyer,['address','email','phone'])+'</p></div><div><div class="label">Account reference</div><p>'+h(d['customer_id'])+'</p><p>'+str(len(d['invoices']))+' finalised invoice(s)</p></div></div>'+summary(d['totals'])+ageing(d['totals'])
    body+='<h3>Invoice balances</h3><table><colgroup><col style="width:30%">'+('<col style="width:14%">'*5)+'</colgroup><thead><tr><th>Invoice / dates</th><th class="num">Original</th><th class="num">Credits</th><th class="num">Net paid</th><th class="num">Owed</th><th class="num">Refund due</th></tr></thead><tbody>'
    for r in d['invoices']:
        label=h(r['number'])+'<br><span class="small">Issued '+h(r['invoice_date'])+'<br>Due '+h(r['due_date'])+'<br>'+h(r['title'])+'</span>'
        if r['invoice_customer_name']!=buyer['name']:label+='<br><span class="small">Invoice name: '+h(r['invoice_customer_name'])+'</span>'
        body+='<tr><td>'+label+'</td>'+''.join('<td class="num">'+amount(r[k])+'</td>' for k in ('total_cents','credit_cents','net_paid_cents','balance_cents','refund_due_cents'))+'</tr>'
    body+='</tbody></table><h3>Recorded activity</h3><p class="small">Positive amounts increase the account balance; negative amounts reduce it. Reversed entries have zero effect. Entries are shown by entered document/payment date using their current status.</p><table class="statement"><colgroup><col style="width:14%"><col style="width:25%"><col style="width:23%"><col style="width:13%"><col style="width:12%"><col style="width:13%"></colgroup><thead><tr><th>Date</th><th>Document</th><th>Invoice / reference</th><th class="num">Amount</th><th>Status</th><th class="num">Effect</th></tr></thead><tbody>'
    for a in d['activity']:body+='<tr'+(' class="reversed"' if a['status']=='reversed' else '')+'><td>'+h(a['effective_date'])+'</td><td>'+h(KINDS[a['kind']])+'<br>'+h(a['number'])+'</td><td>'+h(a['invoice_number'])+('<br>'+h(a['reference']) if a['reference'] else '')+'</td><td class="num">'+amount(a['amount_cents'])+'</td><td>'+h(a['status'].capitalize())+'</td><td class="num">'+signed(a['effect_cents'])+'</td></tr>'
    body+='</tbody></table>'
    return shell(d,'CUSTOMER STATEMENT',body)
def render_receivables(d):
    body='<p>Filter: '+h({'all':'All finalised invoices','open':'Amounts owed','overdue':'Overdue amounts','refund_due':'Refunds due'}[d['status']])+(' · Search: '+h(d['q']) if d['q'] else '')+'</p>'+summary(d['totals'])+'<p class="small">'+str(d['total'])+' matching customer(s) · '+str(d['totals']['invoice_count'])+' invoice(s). Totals cover all matching rows, regardless of screen pagination.</p>'
    body+='<table><colgroup><col style="width:30%">'+('<col style="width:10%">'*7)+'</colgroup><thead><tr><th>Customer</th>'+''.join('<th class="num">'+h(k)+'</th>' for k in (*LABELS,'Total owed','Refund due'))+'</tr></thead><tbody>'
    for r in d['all_customers']:body+='<tr><td>'+h(r['name'])+'<br><span class="small">'+h(r['id'])+'</span></td>'+''.join('<td class="num">'+amount(r[k])+'</td>' for k in (*BUCKETS,'balance_cents','refund_due_cents'))+'</tr>'
    if not d['all_customers']:body+='<tr><td colspan="8">No matching finalised invoices.</td></tr>'
    body+='</tbody><tfoot><tr><th>Report total</th>'+''.join('<th class="num">'+amount(d['totals'][k])+'</th>' for k in (*BUCKETS,'balance_cents','refund_due_cents'))+'</tr></tfoot></table><p class="small">Ageing is by due date at the current Nassau date. Due today is not overdue. Refunds due do not offset debts on another invoice.</p>'
    return shell(d,'OUTSTANDING BALANCES',body,True)
