"""Inch calibration for flat, front-on reference areas. Legacy previews are unchanged."""
import io,math
from PIL import Image
from product_images import encode_image,checked_bytes

FIELDS={'unit','reference_width','reference_height','left','top','right','bottom','print_width'}
def validate_scale(s):
    if not isinstance(s,dict) or set(s)!=FIELDS or s['unit']!='in':raise ValueError('INVALID_REFERENCE_AREA')
    for k in FIELDS-{'unit'}:
        n=s[k];digits=4 if k in ('left','top','right','bottom') else 3
        if type(n) not in (int,float) or not math.isfinite(n) or abs(n*10**digits-round(n*10**digits))>0.000001:raise ValueError('INVALID_REFERENCE_AREA')
        if k in ('left','top','right','bottom'):
            if not 0<=n<=100:raise ValueError('INVALID_REFERENCE_AREA')
        elif not .001<=n<=2000:raise ValueError('INVALID_REFERENCE_AREA')
    if s['right']<=s['left'] or s['bottom']<=s['top']:raise ValueError('INVALID_REFERENCE_AREA')
    return dict(s)

def geometry(bw,bh,lw,lh,c,rotated_size=None):
    s=validate_scale(c['scale'])
    left=bw*s['left']/100;top=bh*s['top']/100;rw=bw*(s['right']-s['left'])/100;rh=bh*(s['bottom']-s['top'])/100
    if min(rw,rh)<8:raise ValueError('INVALID_REFERENCE_AREA')
    ppi=rw/s['reference_width'];vertical=rh/s['reference_height']
    if abs(ppi/vertical-1)>.01:raise ValueError('REFERENCE_ASPECT_MISMATCH')
    width=s['print_width']*ppi;height=width*lh/lw
    if min(width,height)<1:raise ValueError('PRINT_SIZE_TOO_SMALL')
    # Reject oversize before allocating the artwork, and never silently reduce it.
    angle=math.radians(c['rotation']);co=abs(math.cos(angle));si=abs(math.sin(angle))
    aw,ah=rotated_size or (width*co+height*si,width*si+height*co)
    if aw>rw+1e-6 or ah>rh+1e-6:raise ValueError('PRINT_OUTSIDE_REFERENCE')
    x=max(left,min(left+rw-aw,bw*c['x']/100-aw/2));y=max(top,min(top+rh-ah,bh*c['y']/100-ah/2))
    return {'width_px':width,'height_px':height,'left_px':x,'top_px':y,'rotated_width_px':aw,'rotated_height_px':ah,'ppi':ppi,'reference_left_px':left,'reference_top_px':top,'reference_width_px':rw,'reference_height_px':rh,'print_width_in':s['print_width'],'print_height_in':s['print_width']*lh/lw,'left_in':(x-left)/ppi,'top_in':(y-top)/ppi}

def scaled_artwork(base_size,logo,c):
    bw,bh=base_size;g=geometry(bw,bh,logo.width,logo.height,c)
    artwork=logo.resize((max(1,round(g['width_px'])),max(1,round(g['height_px']))),Image.Resampling.LANCZOS)
    if c['rotation']:artwork=artwork.rotate(-c['rotation'],resample=Image.Resampling.BICUBIC,expand=True)
    # Pixel rounding at the reference edge can exceed a mathematical bound by a
    # pixel; do not rescale or clip the requested physical print size.
    g=geometry(bw,bh,logo.width,logo.height,c,artwork.size)
    return artwork,g

def render_scaled(base,logo,c):
    artwork,g=scaled_artwork(base.size,logo,c)
    base.alpha_composite(artwork,(round(g['left_px']),round(g['top_px'])))
    out=io.BytesIO();base.save(out,format='PNG');return encode_image(out.getvalue())

def measurements(record):
    if 'scale' not in record['config']:return None
    with Image.open(io.BytesIO(checked_bytes(record['logo']))) as image:logo=image.convert('RGBA')
    box=logo.getchannel('A').getbbox()
    if not box:raise ValueError('LOGO_EMPTY')
    logo=logo.crop(box);_,g=scaled_artwork((record['preview']['width'],record['preview']['height']),logo,record['config'])
    return g
