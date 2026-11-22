"""Catalogue-size raster copies; originals are never modified or retained here."""
import base64,hashlib,io,re,warnings
from PIL import Image,ImageOps,UnidentifiedImageError

MAX_INPUT=12_000_000
MAX_PIXELS=24_000_000
MAX_IMAGE=512000

def normalized_image(raw):
    if not isinstance(raw,bytes) or not 1<=len(raw)<=MAX_INPUT:raise ValueError('IMAGE_INPUT_SIZE')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw),formats=('JPEG','PNG','WEBP')) as source:
                if source.width*source.height>MAX_PIXELS or min(source.size)<1:raise ValueError('IMAGE_PIXEL_LIMIT')
                if getattr(source,'n_frames',1)!=1:raise ValueError('IMAGE_ANIMATED')
                source.load();oriented=ImageOps.exif_transpose(source)
                has_alpha='A' in oriented.getbands() or 'transparency' in oriented.info
                image=oriented.convert('RGBA' if has_alpha else 'RGB')
                image.info.clear()
        image.thumbnail((1600,1600),Image.Resampling.LANCZOS)
        # Preserve transparency. Lossy RGB compression is explicitly a catalogue copy.
        for edge,quality in ((1600,90),(1200,85),(900,80),(640,75)):
            image.thumbnail((edge,edge),Image.Resampling.LANCZOS)
            out=io.BytesIO();image.save(out,format='WEBP',quality=quality,method=4,exact=True)
            result=out.getvalue()
            if len(result)<=MAX_IMAGE:return result,image.width,image.height
        raise ValueError('IMAGE_OUTPUT_SIZE')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning,MemoryError):
        raise ValueError('IMAGE_INVALID') from None

def safe_filename(value):
    name=re.sub(r'[^A-Za-z0-9 _().-]','_',str(value).rsplit('/',1)[-1].rsplit('\\',1)[-1])
    name=name.rsplit('.',1)[0].strip(' ._-')[:130] or 'catalogue-image'
    if not name[0].isalnum():name='image-'+name
    return name+'.webp'

def encode_image(raw):
    data,width,height=normalized_image(raw)
    return {'content_base64':base64.b64encode(data).decode('ascii'),'sha256':hashlib.sha256(data).hexdigest(),'width':width,'height':height,'size_bytes':len(data)}

def checked_bytes(record):
    try:
        text=record['content_base64']
        if not isinstance(text,str) or len(text)>682668:raise ValueError()
        raw=base64.b64decode(text,validate=True)
        if not 12<=len(raw)<=MAX_IMAGE or len(raw)!=record['size_bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError()
        with Image.open(io.BytesIO(raw),formats=('WEBP',)) as im:
            if im.size!=(record['width'],record['height']) or not all(1<=n<=1600 for n in im.size) or getattr(im,'n_frames',1)!=1:raise ValueError()
            im.load()
        return raw
    except (ValueError,KeyError,TypeError,OSError,Image.DecompressionBombError):raise ValueError('IMAGE_INTEGRITY_FAILED') from None
