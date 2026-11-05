"""Printable HTML uses saved snapshots only; no network resources or raw markup."""
from html import escape
from decimal import Decimal
from quote_rules import validate_saved_quote

def h(v):return escape(str(v),quote=True)
def amount(v):return f'{Decimal(v)/100:,.2f}'
def money(v):return 'BSD '+amount(v)
def lines_text(v):return h(v).replace('\n','<br>')
def details(d,keys):return '<br>'.join(lines_text(d.get(k,'')) for k in keys if d.get(k))

def render_quote(record):
    d=record['data'];validate_saved_quote(d)
    seller=record['seller_snapshot'];buyer=record['customer_snapshot'];contact=record.get('contact_snapshot') or {}
    number=h(record['number']);draft=record['status']=='draft'
    rows=[]
    for l in d['lines']:
        extra=' · '.join(x for x in (l['finish'],l['placement']) if x)
        rows.append('<tr><td>'+lines_text(l['description'])+('<div class="muted">'+h(extra)+'</div>' if extra else '')+'</td><td class="num">'+h(l['quantity'])+' '+h(l['unit'])+'</td><td class="num">'+amount(round(Decimal(l['unit_price'])*100))+'</td><td class="num">'+h(l['discount_percent'])+'%</td><td class="num">'+h(l['vat_rate'])+'%</td><td class="num">'+amount(l['total_cents'])+'</td></tr>')
    sums=''.join('<div><span>'+name+'</span><strong>'+money(d[key])+'</strong></div>' for name,key in [('Subtotal','subtotal_cents'),('Discount','discount_cents'),('VAT','tax_cents'),('Total','total_cents')])
    notice='<p class="draft">DRAFT — FOR REVIEW</p>' if draft else ''
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+number+'''</title><style>
*{box-sizing:border-box}body{font:14px Arial,sans-serif;color:#20252a;margin:0;background:#f5f6fa}.sheet{max-width:1000px;margin:24px auto;padding:40px;background:white}h1{font-size:30px;color:#b72030;margin:0 0 10px}h2{overflow-wrap:anywhere;font-size:19px;margin:0 0 10px}.heading,.parties{display:flex;justify-content:space-between;gap:24px}.heading>div,.parties>div{flex:1;min-width:0;overflow-wrap:anywhere}.right{text-align:right}.parties{margin:30px 0}.label{color:#656b73;font-size:12px;font-weight:bold;text-transform:uppercase;margin-bottom:8px}p{line-height:1.5}table{width:100%;table-layout:fixed;font-size:12px;border-collapse:collapse;margin:25px 0}thead{display:table-header-group}th{background:#f2f3f5;text-align:left;font-size:12px}td,th{padding:10px 5px;border-bottom:1px solid #ddd;vertical-align:top;overflow-wrap:anywhere}.num{text-align:right;white-space:normal;font-variant-numeric:tabular-nums}.muted{color:#666;font-size:12px;margin-top:7px}.totals{margin-left:auto;width:310px}.totals>div{display:flex;justify-content:space-between;padding:8px;border-bottom:1px solid #eee}.totals>div:last-child{font-size:20px;color:#b72030}.terms{margin-top:28px;border-top:1px solid #ddd;padding-top:18px;overflow-wrap:anywhere}.draft{padding:12px;background:#fff1cf;font-weight:bold}.print-help{max-width:1000px;margin:18px auto;padding:0 15px}.footer{margin-top:30px;font-size:12px;color:#666}tr{break-inside:avoid}@page{size:letter;margin:14mm}@media print{body{background:white;font-size:12px}h1{font-size:26px}h2{font-size:17px}p{margin:8px 0;line-height:1.4}.parties{margin:18px 0}table{margin:18px 0}td,th{padding:8px 5px}.totals>div{padding:6px}.terms{margin-top:18px;padding-top:10px}.footer{margin-top:18px}.draft{padding:8px}.sheet{margin:0;padding:0;max-width:none}.print-help{display:none}a{color:inherit;text-decoration:none}.heading,.parties,.totals{break-inside:avoid}}@media(max-width:650px){.sheet{padding:20px}.heading,.parties{display:block}.right{text-align:left}.scroll{overflow-x:auto}}
</style></head><body><p class="print-help">Use your browser’s Print command to print or save as PDF. <a href="/quotes">Back to quotes</a></p><main class="sheet">'''+notice+'''
<div class="heading"><div><h1>'''+h(seller['name'])+'''</h1><p>'''+details(seller,['address','email','phone','website'])+'''</p>'''+('<p>VAT ID: '+h(seller['tax_id'])+'</p>' if seller.get('tax_id') else '')+'''</div><div class="right"><h2>QUOTE '''+number+'''</h2><p>Date: '''+h(d['quote_date'])+'''<br>Valid until: '''+h(d['valid_until'])+'''<br>Revision: '''+h(record['version'])+'''</p><p>Currency: BSD<br>Prices entered before VAT</p></div></div>
<div class="parties"><div><div class="label">Prepared for</div><strong>'''+h(buyer['name'])+'''</strong><p>'''+details(buyer,['address','email','phone'])+'''</p>'''+('<p>Customer VAT ID: '+h(buyer['tax_id'])+'</p>' if buyer.get('tax_id') else '')+'''</div><div><div class="label">Contact</div><p>'''+details(contact,['name','title','email','phone'])+'''</p></div></div><h2>'''+h(d['title'])+'''</h2>
<div class="scroll"><table><colgroup><col style="width:34%"><col style="width:13%"><col style="width:16%"><col style="width:9%"><col style="width:8%"><col style="width:20%"></colgroup><thead><tr><th>Description</th><th class="num">Quantity</th><th class="num">Unit price<br>BSD</th><th class="num">Disc.</th><th class="num">VAT</th><th class="num">Total incl. VAT<br>BSD</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<section class="totals">'''+sums+'''</section><p class="right">Deposit required ('''+h(d['deposit_percent'])+'''%): <strong>'''+money(d['deposit_cents'])+'''</strong></p>
'''+('<section class="terms"><div class="label">Notes</div><p>'+lines_text(d['notes'])+'</p></section>' if d['notes'] else '')+'''<section class="terms"><div class="label">Terms</div><p>'''+lines_text(d['terms'])+'''</p></section><p class="footer">This is a quotation, not a tax invoice or payment receipt.</p></main></body></html>'''
