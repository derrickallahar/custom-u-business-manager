"""Official, bundled Custom U artwork. No remote images or document mutations."""
from functools import lru_cache
from html import escape
from pathlib import Path
import re

BRAND = Path(__file__).resolve().parent / 'static' / 'brand'

@lru_cache(maxsize=1)
def logo_svg():
    svg = (BRAND / 'custom-u-logo.svg').read_text(encoding='utf-8')
    # Only this bundled, reviewed asset is used; no user-supplied markup.
    svg = re.sub(r'^<\?xml[^>]+>\s*', '', svg)
    svg = re.sub(r'<svg\b', '<svg role="img" aria-label="Custom U" style="display:block;width:176px;max-width:100%;height:auto;margin-bottom:8px"', svg, count=1)
    return svg

def html_logo(name=None):
    legal_name = ('<h1 style="font-size:13px;color:#20242a;margin:0 0 8px">'
                  + escape(str(name)) + '</h1>') if name else ''
    return '<div class="cu-document-brand">' + logo_svg() + legal_name + '</div>'

def pdf_logo(width=156):
    from reportlab.platypus import Image
    from PIL import Image as PILImage
    path = BRAND / 'custom-u-logo.png'
    with PILImage.open(path) as source:
        height = width * source.height / source.width
    logo = Image(str(path), width=width, height=height)
    logo.hAlign = 'LEFT'
    return logo

def draw_logo(canvas, x, top, width=130):
    from PIL import Image
    path = BRAND / 'custom-u-logo.png'
    with Image.open(path) as source:
        height = width * source.height / source.width
    canvas.drawImage(str(path), x, top-height, width=width, height=height, mask='auto')
