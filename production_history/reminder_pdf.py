from branding import pdf_logo
"""A balance reminder, not a newly issued invoice or tax document."""
import io
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from catalogue_pdf import fonts
from reminder_rules import invoice
from reminder_text import stage_label,phase,DEFAULT_MESSAGES,render_message

def render(row,stage,today,test,message=None):
    invoice(row);fonts();out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=(612,792),leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42,invariant=1)
    style=ParagraphStyle('body',fontName='CU-Regular',fontSize=11,leading=17,spaceAfter=10)
    title=ParagraphStyle('title',parent=style,fontName='CU-Bold',fontSize=24,leading=30,textColor=HexColor('#b72030'))
    def p(s,fmt=style):return Paragraph(escape(s),fmt)
    story=[pdf_logo(),Spacer(1,12),p('CUSTOM U',style),p('TEST - INTERNAL CHECK ONLY' if test else {'before_due':'UPCOMING PAYMENT','due_today':'PAYMENT DUE TODAY','overdue':'PAYMENT REMINDER'}[phase(stage)],title),Spacer(1,18),p('Customer: '+row['customer_name']),p('Invoice: '+row['number']),p('Due date: '+row['due_date']),p('Balance checked on: '+today),p('Outstanding: BSD '+format(row['balance_cents']/100,',.2f')),p('Scheduled reminder stage: '+stage_label(stage)),Spacer(1,20),Paragraph(escape(message or render_message(DEFAULT_MESSAGES,row,stage,today)).replace('\n','<br/>'),style),p('This is a reminder of the recorded balance. It is not a new invoice or tax document. No late fee has been added.'),Spacer(1,18),p('Custom U | derrick@custom-u.com')]
    doc.build(story);return out.getvalue()
