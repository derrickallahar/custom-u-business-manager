"""Bounded public HTTPS import. No cookies, application tokens, scripts or proxy use.

Every connection is pinned to a DNS address checked before connecting; TLS still
validates the original hostname. Redirects repeat the complete address check.
"""
import html
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

MAX_HTML = 2_000_000
MAX_DOWNLOAD = 12_000_000
SOURCE_LIMITS = {'supplier':160,'url':2048,'sku':100,'cost':10,'currency':3,'colours':800,'sizes':800,'specifications':4000}

class ImportProblem(ValueError):
    pass

def input_url(value):
    """Remove common clipboard wrappers, then apply the strict URL policy.

    This is only for an explicitly submitted link. Redirects and addresses
    from the supplier page still use public_url without clipboard cleanup.
    """
    if not isinstance(value,str) or len(value)>4096:
        raise ImportProblem('SUPPLIER_INPUT_URL_INVALID')
    value=value.strip().strip('\u200b\ufeff').strip()
    markdown=re.fullmatch(r'\[[^\]\r\n]{0,2048}\]\((https://[^\s]+)\)',value)
    if markdown:value=markdown.group(1)
    elif value.startswith('<https://') and value.endswith('>'):value=value[1:-1]
    # A Markdown-escaped ampersand is not a URL path separator.
    value=value.replace('\\&','&')
    try:return public_url(value)
    except ImportProblem:raise ImportProblem('SUPPLIER_INPUT_URL_INVALID') from None

def public_url(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048 or re.search(r'[\s\x00-\x1f\x7f\\]', value):
        raise ImportProblem('SUPPLIER_URL_INVALID')
    try:
        p = urlsplit(value)
        if p.scheme != 'https' or p.username is not None or p.password is not None or p.port not in (None,443):
            raise ValueError()
        host = (p.hostname or '').encode('idna').decode('ascii').lower()
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', host) or '..' in host or '.' not in host:
            raise ValueError()
        if host.endswith(('.localhost','.local','.internal','.invalid','.test','.example')):
            raise ValueError()
        # No IP literals, shorthand numeric IPs or scoped addresses.
        try: ipaddress.ip_address(host)
        except ValueError: pass
        else: raise ValueError()
        path = quote(p.path or '/', safe='/%:@-._~!$&()*+,;=')
        query = quote(p.query, safe='/%?:@-._~!$&()*+,;=')
        result = urlunsplit(('https',host,path,query,''))
        if len(result)>2048: raise ValueError()
        return result
    except (ValueError,UnicodeError):
        raise ImportProblem('SUPPLIER_URL_INVALID') from None

def public_addresses(host):
    try: answers = socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except OSError: raise ImportProblem('SUPPLIER_UNAVAILABLE') from None
    ips = list(dict.fromkeys(item[4][0] for item in answers))
    if not ips: raise ImportProblem('SUPPLIER_UNAVAILABLE')
    for raw in ips:
        try: ip=ipaddress.ip_address(raw)
        except ValueError: raise ImportProblem('SUPPLIER_ADDRESS_BLOCKED') from None
        special=('192.0.0.0/24','192.88.99.0/24') if ip.version==4 else ('64:ff9b::/96','64:ff9b:1::/48','2001::/23','2002::/16')
        if any(ip in ipaddress.ip_network(net) for net in special) or not ip.is_global or ip.is_multicast or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified or getattr(ip,'ipv4_mapped',None) or getattr(ip,'sixtofour',None) or getattr(ip,'teredo',None):
            raise ImportProblem('SUPPLIER_ADDRESS_BLOCKED')
    return ips

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host,443,timeout=timeout,context=ssl.create_default_context())
        self.address = address
    def connect(self):
        sock = socket.create_connection((self.address,443),self.timeout)
        try: self.sock = self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:
            sock.close()
            raise

def fetch_public(value, *, image=False):
    url=input_url(value); deadline=time.monotonic()+20; limit=MAX_DOWNLOAD if image else MAX_HTML
    for hop in range(4):
        p=urlsplit(url);addresses=public_addresses(p.hostname)
        remaining=deadline-time.monotonic()
        if remaining<=0: raise ImportProblem('SUPPLIER_TIMEOUT')
        connection=PinnedHTTPS(p.hostname,addresses[0],min(8,remaining))
        try:
            connection.request('GET',p.path+('?' + p.query if p.query else ''),headers={
                'User-Agent':'CustomU-Catalogue-Import/106',
                'Accept':'image/png,image/jpeg,image/webp' if image else 'text/html,application/xhtml+xml',
                'Accept-Encoding':'identity','Connection':'close'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location','')
                if not location or hop==3: raise ImportProblem('SUPPLIER_REDIRECT_LIMIT')
                try:url=public_url(urljoin(url,location.strip()))
                except (ValueError,ImportProblem):raise ImportProblem('SUPPLIER_REDIRECT_INVALID') from None
                continue
            if response.status!=200:
                raise ImportProblem('SUPPLIER_PAGE_RESTRICTED' if response.status in (401,403,429) else 'SUPPLIER_UNAVAILABLE')
            content_type=response.getheader('Content-Type','').split(';')[0].strip().lower()
            allowed=('image/png','image/jpeg','image/webp','application/octet-stream') if image else ('text/html','application/xhtml+xml')
            if content_type not in allowed: raise ImportProblem('SUPPLIER_CONTENT_UNSUPPORTED')
            if response.getheader('Content-Encoding','identity').lower() not in ('','identity'):
                raise ImportProblem('SUPPLIER_CONTENT_UNSUPPORTED')
            length=response.getheader('Content-Length')
            if length:
                try: length=int(length)
                except ValueError: raise ImportProblem('SUPPLIER_CONTENT_UNSUPPORTED') from None
                if length<0 or length>limit: raise ImportProblem('SUPPLIER_FILE_TOO_LARGE')
            chunks=[];size=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise ImportProblem('SUPPLIER_TIMEOUT')
                # read1 returns after one underlying read, preserving the overall deadline.
                if connection.sock: connection.sock.settimeout(min(5,remaining))
                chunk=response.read1(min(65536,limit-size+1))
                if not chunk: break
                size+=len(chunk)
                if size>limit: raise ImportProblem('SUPPLIER_FILE_TOO_LARGE')
                chunks.append(chunk)
            if not size: raise ImportProblem('SUPPLIER_CONTENT_UNSUPPORTED')
            return b''.join(chunks),url,content_type
        except (socket.timeout,TimeoutError): raise ImportProblem('SUPPLIER_TIMEOUT') from None
        except (OSError,http.client.HTTPException): raise ImportProblem('SUPPLIER_UNAVAILABLE') from None
        finally: connection.close()
    raise ImportProblem('SUPPLIER_REDIRECT_LIMIT')

def image_attributes(attrs):
    """One displayed product image, with its larger copies ordered first."""
    choices=[attrs.get('data-old-hires'),attrs.get('data-zoom-image')]
    try:
        dynamic=json.loads(attrs.get('data-a-dynamic-image','{}'))
        if isinstance(dynamic,dict):
            ranked=[]
            for link,size in list(dynamic.items())[:40]:
                if isinstance(link,str) and isinstance(size,list) and len(size)==2 and all(type(n) in (int,float) and 0<n<=100000 for n in size):ranked.append((size[0]*size[1],link))
            choices.extend(link for _,link in sorted(ranked,reverse=True))
    except (ValueError,TypeError,RecursionError):pass
    for key in ('data-srcset','srcset'):
        ranked=[]
        for item in (attrs.get(key) or '').split(',')[:40]:
            match=re.fullmatch(r'\s*(\S+)\s+(\d+(?:\.\d+)?)([wx])\s*',item)
            if match:ranked.append((float(match.group(2)),match.group(1)))
        choices.extend(link for _,link in sorted(ranked,reverse=True))
    choices.extend(attrs.get(key) for key in ('data-src','data-original','src'))
    return [x for x in choices if isinstance(x,str) and 0<len(x)<=2048]

def initial_gallery(script):
    """Read only literal JSON for the initially selected gallery; never run JS."""
    marker=re.compile(r'''["']colorImages["']\s*:\s*\{\s*["']initial["']\s*:\s*''')
    for position,match in enumerate(marker.finditer(script)):
        if position>=4:break
        try:rows,_=json.JSONDecoder().raw_decode(script,match.end())
        except (ValueError,RecursionError):continue
        if not isinstance(rows,list):continue
        result=[]
        for row in rows[:24]:
            if isinstance(row,dict):result.append([row.get(key) for key in ('hiRes','large','mainUrl') if isinstance(row.get(key),str)])
        if result:return result
    return []

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta={};self.json_blocks=[];self.script=None;self.script_json=False;self.script_blocks=0;self.title=[];self.in_title=False;self.image_groups=[];self.gallery_groups=[];self.image_links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta':
            key=(a.get('property') or a.get('name') or '').lower()
            if key and len(self.meta)<200: self.meta.setdefault(key,[]).append((a.get('content') or '')[:12000])
            if 'image' in (a.get('itemprop') or '').split() and len(self.image_links)<24:self.image_links.append(a.get('content'))
        if tag=='link' and ('image_src' in (a.get('rel') or '').split() or 'image' in (a.get('itemprop') or '').split()) and len(self.image_links)<24:self.image_links.append(a.get('href'))
        if tag=='img' and (a.get('id') in ('landingImage','imgBlkFront','ebooksImgBlkFront') or 'image' in (a.get('itemprop') or '').split()) and len(self.image_groups)<24:self.image_groups.append(image_attributes(a))
        if tag=='title': self.in_title=True
        if tag=='script':
            self.script_json=(a.get('type') or '').split(';')[0].strip().lower()=='application/ld+json'
            self.script=[] if self.script_json and len(self.json_blocks)<20 or not self.script_json and self.script_blocks<40 else None
            self.script_blocks+=1
    def handle_endtag(self,tag):
        if tag=='title': self.in_title=False
        if tag=='script' and self.script is not None:
            content=''.join(self.script)
            if self.script_json:self.json_blocks.append(content)
            elif len(self.gallery_groups)<24:self.gallery_groups.extend(initial_gallery(content)[:24-len(self.gallery_groups)])
            self.script=None
    def handle_data(self,data):
        if self.script is not None:self.script.append(data)
        elif self.in_title:self.title.append(data)

class TextOnly(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('br','p','li','div'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def clean(value,limit):
    if isinstance(value,list): value=', '.join(clean(x,limit) for x in value[:40])
    elif isinstance(value,dict): value=value.get('name',value.get('value',''))
    if not isinstance(value,(str,int,float)) or isinstance(value,bool):return ''
    t=TextOnly()
    try:t.feed(str(value)[:30000]);value=' '.join(t.parts)
    except Exception:value=str(value)
    return re.sub(r'[\s\x00-\x1f\x7f]+',' ',html.unescape(value)).strip()[:limit]

def parse_page(raw,url):
    if not isinstance(raw,bytes) or len(raw)>MAX_HTML:raise ImportProblem('SUPPLIER_FILE_TOO_LARGE')
    page=Page()
    try:page.feed(raw.decode('utf-8-sig',errors='replace'))
    except Exception:raise ImportProblem('SUPPLIER_CONTENT_UNSUPPORTED') from None
    products=[];nodes=0
    def walk(obj,depth=0):
        nonlocal nodes
        nodes+=1
        if nodes>3000 or depth>20:return
        if isinstance(obj,list):
            for x in obj[:100]:walk(x,depth+1)
        elif isinstance(obj,dict):
            types=obj.get('@type',[]);types=[types] if isinstance(types,str) else types
            if isinstance(types,list) and any(t in ('Product','https://schema.org/Product','http://schema.org/Product') for t in types): products.append(obj)
            for key in ('@graph','mainEntity','itemListElement','item','hasVariant'):
                if key in obj:walk(obj[key],depth+1)
    for block in page.json_blocks:
        try:walk(json.loads(block))
        except (ValueError,RecursionError):continue
    product=products[0] if products else {}
    meta=lambda key:(page.meta.get(key) or [''])[0]
    name=clean(product.get('name') or meta('og:title') or ''.join(page.title),160)
    description=clean(product.get('description') or meta('og:description') or meta('description'),800)
    source={key:'' for key in SOURCE_LIMITS}
    source.update(supplier=clean(meta('og:site_name') or urlsplit(url).hostname,160),url=public_url(url),sku=clean(product.get('sku') or product.get('mpn'),100),colours=clean(product.get('color'),800),sizes=clean(product.get('size'),800))
    specs=[]
    for key in ('brand','material','pattern','width','height','depth','weight'):
        v=clean(product.get(key),500)
        if v:specs.append(key.title()+': '+v)
    props=product.get('additionalProperty',[]);props=props if isinstance(props,list) else [props]
    for prop in props[:30]:
        if isinstance(prop,dict):
            label=clean(prop.get('name'),80);v=clean(prop.get('value'),300)
            if label and v:specs.append(label+': '+v)
    source['specifications']='\n'.join(specs)[:4000]
    offers=product.get('offers',{});offers=offers[0] if isinstance(offers,list) and offers else offers
    if not isinstance(offers,dict):offers={}
    cost=offers.get('price',offers.get('lowPrice',meta('product:price:amount')))
    currency=clean(offers.get('priceCurrency') or meta('product:price:currency'),3).upper()
    if re.fullmatch('[A-Z]{3}',currency):
        source['currency']=currency
        try:
            price=Decimal(str(cost))
            if price.is_finite() and 0<=price<=1000000 and price==price.quantize(Decimal('.01')):source['cost']=format(price,'.2f')
        except (InvalidOperation,ValueError):pass
    candidates=[]
    values=product.get('image',[]);values=values if isinstance(values,list) else [values]
    values+=page.meta.get('og:image',[])+page.meta.get('og:image:secure_url',[])+page.meta.get('twitter:image',[])+page.meta.get('twitter:image:src',[])+page.image_links
    groups=[[value] for value in values[:50]]+page.image_groups+page.gallery_groups
    for group in groups:
        for value in group:
            if isinstance(value,dict):value=value.get('url') or value.get('contentUrl')
            if not isinstance(value,str) or not value.strip() or len(value)>2048:continue
            try:candidate=public_url(urljoin(url,value.strip()))
            except (ValueError,ImportProblem):continue
            # Unsupported data/GIF/SVG placeholders are not usable raster choices.
            if urlsplit(candidate).path.lower().endswith(('.gif','.svg','.ico')):continue
            if candidate not in candidates:candidates.append(candidate)
            break
        if len(candidates)>=12:break
    if not name and not description and not candidates:raise ImportProblem('SUPPLIER_NO_PRODUCT_DETAILS')
    warnings=['Review every field. Availability, quantity breaks, options, taxes and freight may change the supplier price.']
    if not products:warnings.append('No structured product data was found; this is a page summary and may describe a collection rather than one product.')
    if len(products)>1:warnings.append('This page contains several products or variants. The first product is shown; confirm the exact item and options.')
    if not source['cost']:warnings.append('No unambiguous supplier price was found. Enter it manually if needed.')
    if not candidates:warnings.append('No supported product image links were found in the page received. You can upload a PNG, JPG or WebP image manually.')
    return {'source_url':source['url'],'product':{'name':name,'description':description,'category':clean(product.get('category'),80)},'supplier':source,'images':candidates,'warnings':warnings}
