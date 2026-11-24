"""Branded, deterministic customer presentations from validated saved content."""
import io
from decimal import Decimal, ROUND_HALF_UP
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from branding import BRAND
from catalogue_pdf import fonts, paragraph, photo
from catalogue_data import validate_document, text
from product_images import checked_bytes
from mockup_render import configuration
from mockup_scale import measurements

W, H = 960, 760
M, CW = 48, 864
RED = HexColor('#b72030')
INK = HexColor('#22252b')
MUTED = HexColor('#626772')
LINE = HexColor('#e5e0dd')
PALE = HexColor('#fbf0f2')
STONE = HexColor('#f4f2ef')
FINISH = {'colour': 'Colour artwork / UV print', 'engraved-dark': 'Engraving concept - dark', 'engraved-light': 'Engraving concept - light'}
PLACEMENT = {'centre': 'Centre', 'left-chest': "Left chest (wearer's left)", 'back': 'Back', 'bottom-right': 'Bottom right', 'upper-left': 'Upper left', 'front': 'Front'}


def words(c, value, x, top, width, height, size=11, bold=False, color=INK):
    return paragraph(c, str(value), x, top, width, height, size, bold, color)


def document(title, subject):
    fonts()
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(W, H), invariant=1, pageCompression=1)
    c.setTitle(title)
    c.setAuthor('Custom U')
    c.setSubject(subject)
    return out, c


def frame(c, customer, page, total, label):
    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, H-8, W, 8, fill=1, stroke=0)
    words(c, 'PREPARED FOR', M, 725, 500, 14, 8, True, MUTED)
    words(c, customer, M, 704, 660, 44, 23, True, RED)
    # Image bytes, rather than the absolute file path, determine the PDF image
    # identifier so offline recovery produces exactly the same document.
    logo = ImageReader(io.BytesIO((BRAND/'custom-u-logo.png').read_bytes()))
    lw, lh = logo.getSize()
    c.drawImage(logo, W-M-138, 728-138*lh/lw, width=138, height=138*lh/lw, mask='auto')
    c.setStrokeColor(LINE)
    c.line(M, 59, W-M, 59)
    words(c, label, M, 43, 640, 15, 8, True, MUTED)
    c.setFont('CU-Regular', 9)
    c.setFillColor(MUTED)
    c.drawRightString(W-M, 31, f'{page:02d} / {total:02d}')


def cover(c, d, raw, total):
    frame(c, d['customer_name'], 1, total, 'CUSTOM U / PRINT YOUR VISION')
    words(c, 'YOUR PRODUCT SELECTION', M, 622, 400, 20, 10, True, RED)
    title_height = words(c, d['title'], M, 581, 380, 142, 36, True)
    if d['intro'].strip():
        words(c, d['intro'], M, min(415, 581-title_height-25), 380, 190, 12, False, MUTED)
    first = d['items'][0]
    photo(c, raw[first['visual_kind']+':'+first['visual_id']], 468, 188, 444, 420)
    c.setFillColor(PALE)
    c.roundRect(M, 90, CW, 78, 6, fill=1, stroke=0)
    words(c, f'{len(d["items"]):02d} SELECTED OPTIONS', M+18, 149, 420, 20, 12, True, RED)
    words(c, 'Prices in BSD before VAT. VAT is shown separately for each option.', M+18, 124, CW-36, 20, 10)
    words(c, 'A selection prepared for your review. Final quantities and specifications are confirmed in your quotation.', M+18, 105, CW-36, 14, 8, False, MUTED)
    c.showPage()


def catalogue_option(c, d, item, raw, index, total):
    frame(c, d['customer_name'], index+1, total, 'CUSTOM U / CLIENT COLLECTION')
    words(c, f'OPTION {index:02d}  /  '+d['title'], M, 647, CW, 26, 9, True, RED)
    words(c, item['name'], M, 610, CW, 56, 29, True)
    words(c, item['description'], M, 544, CW, 52, 11, False, MUTED)
    c.setFillColor(PALE)
    c.roundRect(M, 441, CW, 43, 5, fill=1, stroke=0)
    price = Decimal(item['unit_price'])
    vat = (price*Decimal(item['vat_rate'])/100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    words(c, f'BSD {price:,.2f} / {item["unit"]}', M+15, 474, 350, 31, 19, True, RED)
    words(c, item['finish'] or 'Branding finish to be confirmed', M+390, 472, CW-405, 28, 10)
    photo(c, raw, M+12, 177, CW-24, 252)
    caption = 'BRANDING CONCEPT' if item['visual_kind']=='mockup' else 'PRODUCT VIEW'
    words(c, caption, M, 165, CW, 16, 9, True)
    c.setFillColor(STONE)
    c.roundRect(M, 80, CW, 63, 5, fill=1, stroke=0)
    words(c, 'PLACEMENT / DETAILS', M+15, 130, 400, 12, 8, True, MUTED)
    words(c, item['placement'] or 'To be confirmed with final artwork', M+15, 112, 400, 27, 10)
    words(c, f'Before VAT: BSD {price:,.2f}  |  VAT {item["vat_rate"]}%: BSD {vat:,.2f}', M+450, 128, CW-465, 18, 9, False, MUTED)
    words(c, f'Including VAT: BSD {price+vat:,.2f} / {item["unit"]}', M+450, 108, CW-465, 22, 11, True)
    words(c, 'Concept for review. Final logo, colour, placement and finish require artwork approval. Availability is confirmed in your quotation.', M, 75, CW, 12, 7, False, MUTED)
    c.showPage()


def render_catalogue_presentation(d, assets):
    raw = validate_document(d, assets)
    out, c = document(d['title'], 'Customer product presentation')
    total = len(d['items'])+1
    cover(c, d, raw, total)
    for index, item in enumerate(d['items'], 1):
        catalogue_option(c, d, item, raw[item['visual_kind']+':'+item['visual_id']], index, total)
    c.save()
    return out.getvalue()


def render_mockup_presentation(record):
    for key in ('title', 'customer_name', 'product_name'):
        text(record[key], 160, True)
    config = configuration(record['config'])
    raw = checked_bytes(record['preview'])
    size = measurements(record)
    out, c = document(record['title'], 'Customer branding concept')
    frame(c, record['customer_name'], 1, 1, 'CUSTOM U / CLIENT MOCKUP')
    words(c, 'BRANDING CONCEPT  /  FOR REVIEW', M, 647, CW, 16, 9, True, RED)
    words(c, record['product_name'], M, 612, CW, 62, 29, True)
    words(c, record['title'], M, 540, CW, 35, 13, False, MUTED)
    c.setFillColor(PALE)
    c.roundRect(M, 458, CW, 39, 5, fill=1, stroke=0)
    words(c, FINISH[config['finish']], M+15, 484, CW-30, 22, 13, True, RED)
    photo(c, raw, M+10, 166, CW-20, 280)
    c.setFillColor(STONE)
    c.roundRect(M, 80, CW, 73, 5, fill=1, stroke=0)
    words(c, 'PLACEMENT', M+15, 139, 400, 12, 8, True, MUTED)
    words(c, PLACEMENT[config['placement']]+' starting point; final placement is shown above.', M+15, 119, 400, 32, 10)
    words(c, 'PRINT SIZE', M+450, 139, CW-465, 12, 8, True, MUTED)
    if size:
        value = f'{size["print_width_in"]:.3f}'.rstrip('0').rstrip('.')+' x '+f'{size["print_height_in"]:.3f}'.rstrip('0').rstrip('.')+' in'
        words(c, value, M+450, 119, CW-465, 20, 13, True)
        words(c, 'Based on the saved reference dimensions; verify before production.', M+450, 98, CW-465, 12, 7, False, MUTED)
    else:
        words(c, 'To be confirmed with production artwork.', M+450, 119, CW-465, 30, 10)
    words(c, 'Concept artwork. Final logo, colour, size and finish require artwork approval. This presentation is not a full-size production file.', M, 75, CW, 12, 7, False, MUTED)
    c.showPage()
    c.save()
    return out.getvalue()
