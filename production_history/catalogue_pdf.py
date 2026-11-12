"""Offline deterministic catalogue PDF. No network fetches or external assets."""
import io,threading
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from PIL import Image
from catalogue_data import validate_document

_font_lock=threading.Lock()
ROOT=Path(__file__).resolve().parent
W,H=595.28,841.89
RED=HexColor('#b72030');INK=HexColor('#202530');MUTED=HexColor('#636a75');LINE=HexColor('#e0e2e7')
def fonts():
    with _font_lock:
        if 'CU-Regular' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('CU-Regular',str(ROOT/'fonts/DejaVuSans.ttf')))
            pdfmetrics.registerFont(TTFont('CU-Bold',str(ROOT/'fonts/DejaVuSans-Bold.ttf')))
def paragraph(c,text,x,top,width,maxheight,size=11,bold=False,color=INK):
    safe=escape(text).replace('\r\n','\n').replace('\r','\n').replace('\n','<br/>')
    while size>=6:
        p=Paragraph(safe,ParagraphStyle('cu',fontName='CU-Bold' if bold else 'CU-Regular',fontSize=size,leading=size*1.4,textColor=color,splitLongWords=True))
        _,height=p.wrap(width,maxheight)
        if height<=maxheight:p.drawOn(c,x,top-height);return height
        size-=.5
    raise ValueError('CATALOGUE_TEXT_TOO_LONG')
def photo(c,raw,x,y,width,height):
    with Image.open(io.BytesIO(raw)) as source:
        rgba=source.convert('RGBA');im=Image.new('RGB',rgba.size,'white');im.paste(rgba,mask=rgba.getchannel('A'))
        scale=min(width/im.width,height/im.height);rw,rh=im.width*scale,im.height*scale
        c.drawImage(ImageReader(im),x+(width-rw)/2,y+(height-rh)/2,rw,rh,mask='auto')
def header(c,page,total):
    c.setFillColor(RED);c.rect(0,H-8,W,8,fill=1,stroke=0)
    c.setFillColor(INK);c.setFont('CU-Bold',20);c.drawString(38,H-48,'CUSTOM')
    c.setFillColor(RED);c.drawString(135,H-48,'U')
    c.setFont('CU-Regular',8);c.setFillColor(MUTED);c.drawRightString(W-38,H-42,'CLIENT CATALOGUE')
    c.setStrokeColor(LINE);c.line(38,43,W-38,43)
    c.setFont('CU-Regular',8);c.drawString(38,27,'Custom U | Print Your Vision.');c.drawRightString(W-38,27,f'{page} / {total}')
def render_catalogue(document,assets):
    raw=validate_document(document,assets);fonts();items=document['items'];total=1+(len(items)+1)//2
    out=io.BytesIO();c=canvas.Canvas(out,pagesize=(W,H),invariant=1,pageCompression=1);c.setTitle(document['title']);c.setAuthor('Custom U');c.setSubject('Customer product options')
    header(c,1,total)
    paragraph(c,'PREPARED FOR',38,746,W-76,24,9,True,RED)
    paragraph(c,document['customer_name'],38,719,W-76,68,21,True)
    paragraph(c,document['title'],38,630,W-76,84,27,True)
    paragraph(c,document['intro'],38,531,W-76,110,11)
    first=items[0];photo(c,raw[first['visual_kind']+':'+first['visual_id']],70,153,W-140,248)
    c.setFillColor(RED);c.roundRect(38,74,W-76,54,7,fill=1,stroke=0)
    paragraph(c,f'{len(items)} selected options | Prices in BSD',54,112,W-108,20,11,True,white)
    paragraph(c,'Prepared for review. Availability and final specifications are confirmed in your quotation.',54,93,W-108,14,8,False,white)
    c.showPage()
    for offset in range(0,len(items),2):
        header(c,2+offset//2,total)
        paragraph(c,document['customer_name'],38,758,W-76,28,11,True)
        for index,x in enumerate(items[offset:offset+2],offset+1):
            top=712-(index-1-offset)*306;y=top-278
            c.setStrokeColor(LINE);c.setFillColor(white);c.roundRect(38,y,W-76,278,8,fill=1,stroke=1)
            paragraph(c,f'OPTION {index:02d} | {x["product_code"]}',52,top-14,W-104,24,8,True,RED)
            photo(c,raw[x['visual_kind']+':'+x['visual_id']],52,y+34,195,204)
            tx=265;tw=W-317
            paragraph(c,x['name'],tx,top-40,tw,48,14,True)
            paragraph(c,x['description'],tx,top-94,tw,84,9)
            spec=' | '.join(v for v in (x['finish'],x['placement']) if v)
            paragraph(c,spec,tx,top-183,tw,34,8,False,MUTED)
            price=Decimal(x['unit_price']);vat=(price*Decimal(x['vat_rate'])/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            paragraph(c,f'BSD {price:,.2f} / {x["unit"]}',tx,top-222,tw,25,13,True,RED)
            paragraph(c,f'Before VAT | VAT {x["vat_rate"]}%: BSD {vat:,.2f}\nIncluding VAT: BSD {price+vat:,.2f}',tx,top-247,tw,26,8)
            if x['visual_kind']=='mockup':paragraph(c,'Illustrative branding preview',52,y+22,195,14,7,False,MUTED)
        paragraph(c,'Prices are per unit. Availability, quantities and final specifications are confirmed in your quotation. Mockups are visual references; production artwork requires separate approval.',38,83,W-76,31,8,False,MUTED)
        c.showPage()
    c.save();return out.getvalue()
