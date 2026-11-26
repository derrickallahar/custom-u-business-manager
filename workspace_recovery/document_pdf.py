from branding import pdf_logo
"""Deterministic PDFs from saved snapshots and current bank instructions."""
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

def render_document(kind, record, payment_summary=None):
    if kind not in ('quote','invoice'):raise ValueError('DOCUMENT_KIND')
    invoice=kind=='invoice'
    if invoice:validate_invoice_document(record)
    from invoice_payment_summary import payment_view
    paid_view=payment_view(record,payment_summary) if invoice and payment_summary is not None else None
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
    styles['bank']=ParagraphStyle('bank',parent=styles['body'],spaceAfter=2)
    def p(value,style='body'):
        return Paragraph(escape(str(value)).replace('\r\n','\n').replace('\r','\n').replace('\n','<br/>'),styles[style])
    def details(obj,keys):return '\n'.join(str(obj[k]) for k in keys if obj.get(k))
    story=[]
    if banner:story += [p(banner,'label'),Spacer(1,8)]
    seller_header=[pdf_logo(),Spacer(1,8),p(seller['name'],'small'),p(details(seller,['address','email','phone','website']),'small')]
    if seller.get('tax_id'):seller_header.append(p('VAT ID: '+seller['tax_id'],'small'))
    dates=('Invoice date: '+m['invoice_date']+'\nPayment due: '+m['due_date']+('\nEarlier supply/payment: '+m['supply_date'] if m['supply_date'] else '')+('\nSource quote: '+q['number'] if record['quote_id'] else '')) if invoice else 'Quote date: '+d['quote_date']+'\nValid until: '+d['valid_until']
    document_header=[p(title,'heading'),p(number,'heading'),p(dates+'\nRevision: '+str(record['version'])+'\nCurrency: BSD\nUnit prices before VAT','small')]
    header=Table([[seller_header,document_header]],colWidths=[300,240],hAlign='LEFT')
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story += [header,Spacer(1,16)]
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
    deposit=q.get('original_quote_data',d)
    summary=[sums]+([Spacer(1,8),p(('Quoted deposit requirement' if invoice else 'Deposit required')+' ('+deposit['deposit_percent']+'%): '+money(deposit['deposit_cents']),'small')] if not invoice or record['quote_id'] else [])
    compact_payments=paid_view is not None and len(paid_view['payments'])<=4
    if compact_payments:
        styles['payment-small']=ParagraphStyle('payment-small',parent=styles['small'],spaceAfter=0,leading=11)
        summary += [Spacer(1,8),p('Payment status: '+paid_view['status'],'label')]
        date_text=('Date paid: '+paid_view['date_paid']) if paid_view['date_paid'] else ('Last payment: '+paid_view['last_payment_date']) if paid_view['last_payment_date'] else ''
        if date_text:summary.append(p(date_text,'small'))
        if paid_view['payments']:
            entries=Table([[p(x['date_label']+' · '+x['number'],'payment-small'),p(money(x['amount_cents']),'payment-small')] for x in paid_view['payments']],colWidths=[210,90],hAlign='RIGHT')
            entries.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
            summary += [entries,Spacer(1,5)]
        settlement=Table([[p(x['label']),p(money(x['amount_cents']),'label')] for x in paid_view['totals']],colWidths=[180,120],hAlign='RIGHT')
        settlement.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#dedee4'))]))
        summary += [settlement,p(paid_view['note'],'small')]
    story += [KeepTogether(summary)]
    if paid_view and not compact_payments:
        date_text=('Date paid: '+paid_view['date_paid']) if paid_view['date_paid'] else ('Last payment: '+paid_view['last_payment_date']) if paid_view['last_payment_date'] else ''
        heading=p('Payment status: '+paid_view['status'],'heading');heading.keepWithNext=True
        story += [Spacer(1,16),heading]
        if date_text:
            date_line=p(date_text,'label');date_line.keepWithNext=True;story.append(date_line)
        if paid_view['payments']:
            rows=[[p(x,'head') for x in ['Payment date','Receipt','Amount received']]]
            rows += [[p(x['date_label'],'cell'),p(x['number'],'cell'),p(money(x['amount_cents']),'cell')] for x in paid_view['payments']]
            history=Table(rows,colWidths=[160,200,180],repeatRows=1,hAlign='LEFT',splitByRow=1)
            history.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#f0f1f5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#dedee4')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            story += [history,Spacer(1,8)]
        totals=Table([[p(x['label']),p(money(x['amount_cents']),'label')] for x in paid_view['totals']],colWidths=[180,120],hAlign='RIGHT')
        totals.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#dedee4'))]))
        story += [KeepTogether([totals,p(paid_view['note'],'small')])]
    elif invoice and not draft and paid_view is None:
        story += [Spacer(1,12),p('Payment status is not included in this copy.','small')]
    for heading,text in [('Notes',m.get('notes') if invoice else d['notes']),('Terms',m.get('terms') if invoice else d['terms'])]:
        if text:
            heading_line=p(heading,'label');heading_line.keepWithNext=True
            story += [Spacer(1,12),heading_line,p(text)]
    ending=('Test document only. No amount is payable.' if test else 'Draft for review. Not an issued invoice.' if draft else 'The invoice total is unchanged by payments. Payment details reflect the records included in this copy.') if invoice else 'This is a quotation, not a tax invoice or payment receipt.'
    story += [Spacer(1,14),p(ending,'small')]
    def footer(c,document):
        c.saveState();c.setStrokeColor(RED);c.line(36,45,576,45);c.setFillColor(GREY);c.setFont('CU-Regular',7)
        c.drawString(36,31,number+(' | '+banner if banner else ''));c.drawRightString(576,31,'Page '+str(document.page));c.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=partial(Canvas,invariant=1))
    return out.getvalue()
