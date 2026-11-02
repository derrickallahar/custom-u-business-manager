"""Permission-checked staging print previews; no issuance, email, or balance changes."""
import html, json
from document_terms import terms_for_document

def render_document(kind, record):
    if kind not in ('quotes','invoices'): raise ValueError('Invalid document kind')
    esc=lambda value:html.escape(str(value if value is not None else ''))
    def money(value):
        if type(value) is not int: raise ValueError('Invalid saved cents')
        return 'BSD $'+format(value/100,',.2f')
    lines=json.loads(record.get('lines_json') or 'null')
    if not isinstance(lines,list):raise ValueError('Missing saved line items')
    rows=[]
    for line in lines:
        qty=line.get('quantity');unit=line.get('unit_cents')
        if type(qty) is not int or qty<=0 or type(unit) is not int or unit<0:raise ValueError('Invalid saved line')
        rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [line.get('name',''),line.get('method',''),line.get('logo_location',''),qty,money(unit),money(qty*unit)])+'</tr>')
    saved={'terms_text':record['terms_text']} if 'terms_text' in record else None
    terms=terms_for_document('quote' if kind=='quotes' else 'invoice',saved)
    label='Saved terms' if saved is not None else 'Proposed terms for new documents — preview only'
    balance=''
    if kind=='invoices':
        balance='<p>Paid: '+esc(money(record['paid_cents']))+' · Balance: '+esc(money(record['total_cents']-record['paid_cents']))+'</p><p>Due date: '+esc(record.get('due_date'))+'</p>'
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Custom U test document</title><style>body{font:15px system-ui;max-width:1000px;margin:40px auto;padding:20px;color:#222}h1{color:#bc2031}table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}.notice{padding:16px;background:#fff0cc}p{white-space:pre-wrap}@media print{body{margin:0;padding:0;font-size:11pt}thead{display:table-header-group}tr{break-inside:avoid}}</style><h1>CUSTOM U · '+esc(kind[:-1].title())+' '+esc(record['number'])+'</h1><p class="notice">FICTIONAL STAGING PREVIEW — NOT A VALID COMMERCIAL OR TAX DOCUMENT</p><p>Use your browser’s Print command to print or save as PDF.</p><p>Status: '+esc(record['status'])+' · Created: '+esc(record.get('created_at'))+'</p><p>Customer reference: '+esc(record.get('customer_id'))+'</p><table><thead><tr><th>Item</th><th>Finish</th><th>Placement</th><th>Quantity</th><th>Unit price</th><th>Line total</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table><h2>Saved total: '+esc(money(record['total_cents']))+'</h2>'+balance+'<h2>'+label+'</h2><p>'+esc(terms)+'</p><p>No fees are calculated or applied by this preview. VAT is not separately calculated in this staging preview. Existing records are not modified.</p></html>').encode('utf-8')
