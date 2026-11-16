"""Version 109: deterministic PDFs from saved quote/invoice snapshots only."""
import io
from functools import partial
from xml.sax.saxutils import escape
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from catalogue_pdf import fonts
from quote_rules import validate_saved_quote
from invoice_rules import validate_invoice_document
from quote_print import money, amount

RED=HexColor('#b72030'); INK=HexColor('#202530'); GREY=HexColor('#616875')

def render_document(kind, record):
    if kind not in ('quote','invoice'):raise ValueError('DOCUMENT_KIND')
    invoice=kind=='invoice'
    if invoice:validate_invoice_document(record)
    q=record['quote_snapshot'] if invoice else record
    d=q['data'];validate_saved_quote(d);fonts()
    m=record['details'] if invoice else {}
    seller=q['seller_snapshot'];buyer=dict(q['customer_snapshot']);contact=q.get('contact_snapshot') or {}
    if invoice:buyer.update(address=m['billing_address'],tax_id=m['billing_tax_id'])
    test=invoice and record['is_test'];draft=record['status']!='issued'
    title=('VAT INVOICE' if m['document_type']=='vat_invoice' else 'VAT SALES RECEIPT') if invoice else 'QUOTATION'
    banner='TEST - NOT A COMMERCIAL OR TAX DOCUMENT' if test else 'DRAFT - FOR REVIEW' if draft else ''
    number=record['number'];out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=(612,792),leftMargin=36,rightMargin=36,topMargin=42,bottomMargin=60,title=title+' '+number,author=seller['name'],pageCompression=1,invariant=1)
    styles={}
    for name,size,bold,col in [('body',9,False,INK),('small',8,False,GREY),('title',22,True,RED),('heading',13,True,INK),('label',9,True,RED),('cell',8,False,INK),('head',8,True,INK)]:
        styles[name]=ParagraphStyle(name,fontName='CU-Bold' if bold else 'CU-Regular',fontSize=size,leading=size*1.4,textColor=col,spaceAfter=5,splitLongWords=True)
    def p(value,style='body'):
        return Paragraph(escape(str(value)).replace('\r\n','\n').replace('\r','\n').replace('\n','<br/>'),styles[style])
    def details(obj,keys):return '\n'.join(str(obj[k]) for k in keys if obj.get(k))
    story=[]
    if banner:story += [p(banner,'label'),Spacer(1,8)]
    story += [p(seller['name'],'title'),p(details(seller,['address','email','phone','website']),'small')]
    if seller.get('tax_id'):story += [p('VAT ID: '+seller['tax_id'],'small')]
    story += [Spacer(1,12),p(title+' '+number,'heading')]
    dates=('Invoice date: '+m['invoice_date']+'   |   Due: '+m['due_date']+('\nEarlier supply/payment: '+m['supply_date'] if m['supply_date'] else '')+'\nSource quote: '+q['number']) if invoice else 'Quote date: '+d['quote_date']+'   |   Valid until: '+d['valid_until']
    story += [p(dates+'\nRevision: '+str(record['version'])+'   |   Currency: BSD   |   Unit prices before VAT','small'),Spacer(1,12)]
    parties=Table([[p('BILLED TO' if invoice else 'PREPARED FOR','label'),p('CONTACT','label')],[p(details(buyer,['name','address','email','phone'])+('\nVAT ID: '+buyer['tax_id'] if buyer.get('tax_id') else '')),p(details(contact,['name','title','email','phone']))]],colWidths=[300,240],hAlign='LEFT')
    parties.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story += [parties,Spacer(1,10),p(d['title'],'heading')]
    labels=['Description','Quantity','Unit price\nBSD','Discount\n% / BSD','Net excl. VAT\nBSD','VAT\n% / BSD'] if invoice else ['Description','Quantity','Unit price\nBSD','Discount','VAT','Total incl. VAT\nBSD']
    rows=[[p(x,'head') for x in labels]]
    for i,line in enumerate(d['lines']):
        extra=' | '.join(x for x in (line['finish'],line['placement']) if x)
        description=line['description']+('\n'+extra if extra else '')
        if invoice:
            values=[description,line['quantity']+'\n'+line['unit'],line['unit_price'],line['discount_percent']+'%\n'+amount(line['discount_cents']),amount(line['net_cents']),(m['tax_codes'][i] or '?')+' '+line['vat_rate']+'%\n'+amount(line['tax_cents'])]
        else:values=[description,line['quantity']+'\n'+line['unit'],line['unit_price'],line['discount_percent']+'%',line['vat_rate']+'%',amount(line['total_cents'])]
        rows.append([p(x,'cell') for x in values])
    table=Table(rows,colWidths=[195,55,75,55,80,80],repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),HexColor('#f0f1f5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#fafafa')]),('LINEBELOW',(0,0),(-1,0),.8,RED),('LINEBELOW',(0,1),(-1,-1),.3,HexColor('#dedee4')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story += [table,Spacer(1,12)]
    if invoice:story += [p('T: taxable | Z: zero-rated | E: exempt','small')]
    totals=[('Subtotal',d['subtotal_cents']),('Discount',d['discount_cents'])]
    if invoice:totals += [('Net before VAT',d['subtotal_cents']-d['discount_cents'])]
    totals += [('VAT',d['tax_cents']),('Invoice total' if invoice else 'Quote total',d['total_cents'])]
    sums=Table([[p(k),p(money(v),'label' if i==len(totals)-1 else 'body')] for i,(k,v) in enumerate(totals)],colWidths=[150,150],hAlign='RIGHT')
    sums.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#dedee4')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [KeepTogether([sums,Spacer(1,8),p(('Quoted deposit requirement' if invoice else 'Deposit required')+' ('+d['deposit_percent']+'%): '+money(d['deposit_cents']),'small')])]
    for heading,text in [('Notes',m.get('notes') if invoice else d['notes']),('Terms',m.get('terms') if invoice else d['terms'])]:
        if text:story += [Spacer(1,12),p(heading,'label'),p(text)]
    ending=('Test document only. No amount is payable.' if test else 'Draft for review. Not an issued invoice.' if draft else 'This document states the invoice total. Payments received are acknowledged separately.') if invoice else 'This is a quotation, not a tax invoice or payment receipt.'
    story += [Spacer(1,14),p(ending,'small')]
    def footer(c,document):
        c.saveState();c.setStrokeColor(RED);c.line(36,45,576,45);c.setFillColor(GREY);c.setFont('CU-Regular',7)
        c.drawString(36,31,number+(' | '+banner if banner else ''));c.drawRightString(576,31,'Page '+str(document.page));c.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=partial(Canvas,invariant=1))
    return out.getvalue()
