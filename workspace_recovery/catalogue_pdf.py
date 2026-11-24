"""Offline deterministic catalogue PDF. No network fetches or external assets."""
import io,threading
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

_font_lock=threading.Lock()
ROOT=Path(__file__).resolve().parent
INK=HexColor('#202530')
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
        # Embed a compressed presentation copy; lossless RGB inflation can make
        # ordinary two-product catalogues exceed the existing email size limit.
        encoded=io.BytesIO();im.save(encoded,format='JPEG',quality=90,optimize=True)
        encoded.seek(0)
        c.drawImage(ImageReader(encoded),x+(width-rw)/2,y+(height-rh)/2,rw,rh)
def render_catalogue(document,assets):
    # The same presentation is used by preview, downloads, email and recovery.
    from presentation_pdf import render_catalogue_presentation
    return render_catalogue_presentation(document,assets)
