"""Network attestation and administrator controls. Trust only the configured DO ingress."""
import hashlib,hmac,ipaddress,json,os,re
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import request,jsonify,has_request_context


def gateway_key():
    secret=os.getenv('CUSTOMU_NETWORK_GATEWAY_SECRET') or os.getenv('CUSTOMU_EMAIL_SIGNING_SECRET','')
    if len(secret)<32:return None
    return hmac.new(secret.encode(),b'custom-u-network-access-118',hashlib.sha256).hexdigest()


def client_ip():
    if not has_request_context() or os.getenv('CUSTOMU_NETWORK_PROXY','')!='digitalocean':return None
    raw=request.headers.get('do-connecting-ip','')
    try:
        address=ipaddress.ip_address(raw)
        return str(address) if address.is_global else None
    except ValueError:return None


def gateway_headers():
    key=gateway_key();ip=client_ip()
    return {'x-customu-gateway':key,'x-customu-client-ip':ip} if key and ip else {}


def local_time(value):
    if value is None:return None
    if not isinstance(value,str) or not re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}',value):raise ValueError('INVALID_ACCESS_DATES')
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('America/Nassau')).isoformat()


def install(app,provider,session,root,failure):
    def call(rec,p):
        result=json.loads(provider.call('/rest/v1/rpc/custom_u_controls_118',rec['token'],{'payload':p},limit=1000000))
        if not isinstance(result,dict):raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:raise failure(result['error'],403 if result['error']=='ACCESS_DENIED' else 409 if result['error']=='VERSION_CONFLICT' else 400)
        return result
    def admin():
        rec,me=session()
        if me.get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return rec
    @app.get('/admin-controls')
    def admin_controls_page():return app.response_class((root/'static/admin-controls.html').read_bytes(),mimetype='text/html')
    @app.get('/admin-controls.js')
    def admin_controls_script():return app.response_class((root/'static/admin-controls.js').read_bytes(),mimetype='text/javascript')
    @app.get('/discounts.js')
    def admin_discount_script():return app.response_class((root/'static/discounts.js').read_bytes(),mimetype='text/javascript')
    @app.get('/api/admin-controls')
    def admin_controls_view():
        result=call(admin(),{'op':'view'});result.update(current_ip=client_ip(),gateway_ready=bool(gateway_key()),proxy_ready=os.getenv('CUSTOMU_NETWORK_PROXY')=='digitalocean')
        return jsonify(result)
    @app.get('/api/customer-discounts/<ident>')
    def customer_discount(ident):
        rec,me=session()
        if not re.fullmatch(r'[a-f0-9-]{36}',ident):raise failure('INVALID_REQUEST',400)
        return jsonify(call(rec,{'op':'discount_get','customer_id':ident}))
    @app.post('/api/admin-controls/action')
    def admin_controls_action():
        rec=admin();request.max_content_length=8192;p=request.get_json()
        fields={'network_save':{'id','label','cidr','active','version'},'grant_save':{'employee_id','starts_at','ends_at','reason','active','version'},'discount_save':{'customer_id','percent','note','version'},'policy_save':{'enabled','version'},'numbering_save':{'quote_next','invoice_next','version'}}
        if not isinstance(p,dict) or p.get('op') not in fields or set(p)!=fields[p['op']]|{'op'}:raise failure('INVALID_REQUEST',400)
        try:
            if p['op']=='network_save':
                network=ipaddress.ip_network(p['cidr'],strict=True)
                if not network.is_global or network.prefixlen<(24 if network.version==4 else 48):raise ValueError('INVALID_NETWORK')
                p['cidr']=str(network)
            if p['op']=='grant_save':
                p['starts_at']=local_time(p['starts_at']);p['ends_at']=local_time(p['ends_at'])
            if p['op']=='policy_save' and p.get('enabled') is True:
                key=gateway_key();ip=client_ip()
                if not key:raise failure('GATEWAY_SETUP_REQUIRED',409)
                if not ip:raise failure('NETWORK_SOURCE_UNAVAILABLE',409)
                p.update(gateway_hash=hashlib.sha256(key.encode()).hexdigest(),current_ip=ip)
        except (ValueError,TypeError):raise failure('INVALID_REQUEST',400) from None
        result=call(rec,p)
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return jsonify(result)
