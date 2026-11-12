"""Deterministic catalogue mockups. Never alters the source product or logo."""
import base64,hashlib,io,math
from PIL import Image,ImageOps
from product_images import encode_image,checked_bytes

FAMILIES={'generic':('centre',),'shirt':('centre','left-chest','back'),'journal':('centre','bottom-right','upper-left'),'drinkware':('centre','front')}
FINISHES=('colour','engraved-dark','engraved-light')

def configuration(value):
    if not isinstance(value,dict) or set(value)!={'x','y','width','rotation','finish','family','placement'}:raise ValueError('INVALID_MOCKUP')
    for k,lo,hi in (('x',0,100),('y',0,100),('width',1,100),('rotation',-180,180)):
        n=value[k]
        if type(n) not in (int,float) or not math.isfinite(n) or not lo<=n<=hi or abs(n*10-round(n*10))>0.000001:raise ValueError('INVALID_MOCKUP')
    if any(not isinstance(value[k],str) for k in ('family','placement','finish')):raise ValueError('INVALID_MOCKUP')
    if value['family'] not in FAMILIES or value['placement'] not in FAMILIES[value['family']] or value['finish'] not in FINISHES:raise ValueError('INVALID_MOCKUP')
    return dict(value)

def render(base_record,logo_record,config):
    c=configuration(config)
    with Image.open(io.BytesIO(checked_bytes(base_record))) as source:base=source.convert('RGBA')
    with Image.open(io.BytesIO(checked_bytes(logo_record))) as source:logo=source.convert('RGBA')
    # Trim transparent margins for predictable auto-fit; preserve opaque artwork.
    box=logo.getchannel('A').getbbox()
    if not box:raise ValueError('LOGO_EMPTY')
    logo=logo.crop(box)
    if c['finish']!='colour':
        tint=(65,55,45) if c['finish']=='engraved-dark' else (220,218,210)
        ink=Image.new('RGBA',logo.size,tint+(255,));ink.putalpha(logo.getchannel('A'));logo=ink
    w=max(1,round(base.width*c['width']/100));h=max(1,round(w*logo.height/logo.width))
    scale=min(1,base.width/w,base.height/h);w=max(1,round(w*scale));h=max(1,round(h*scale))
    logo=logo.resize((w,h),Image.Resampling.LANCZOS)
    if c['rotation']:logo=logo.rotate(-c['rotation'],resample=Image.Resampling.BICUBIC,expand=True)
    # Keep the complete rotated logo on the image. No silent clipping.
    logo.thumbnail(base.size,Image.Resampling.LANCZOS)
    x=max(0,min(base.width-logo.width,round(base.width*c['x']/100-logo.width/2)))
    y=max(0,min(base.height-logo.height,round(base.height*c['y']/100-logo.height/2)))
    base.alpha_composite(logo,(x,y))
    out=io.BytesIO();base.save(out,format='PNG');return encode_image(out.getvalue())
