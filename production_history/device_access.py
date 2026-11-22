"""Approved browser gate for every Business Manager staff session."""
import hashlib,re,secrets,json
from flask import request
COOKIE='__Host-customu_device_115'
def digest():
    value=request.cookies.get(COOKIE,'')
    return hashlib.sha256(value.encode()).hexdigest() if re.fullmatch(r'[A-Za-z0-9_-]{64}',value) else None
def mobile(hint=False):
    ua=request.headers.get('User-Agent','')[:1500]
    return hint is True or request.headers.get('Sec-CH-UA-Mobile')=='?1' or bool(re.search(r'Android|iPhone|iPad|iPod|Mobile|Tablet|Windows Phone|IEMobile|Silk/',ua,re.I))
def authorize(provider,rec,me,failure,hint=False):
    if me.get('role')=='admin':return
    if mobile(hint):raise failure('ADMIN_MOBILE_ONLY',403)
    value=digest()
    if not value or rec.get('device_digest',value)!=value:raise failure('APPROVED_COMPUTER_REQUIRED',403)
    try:result=json.loads(provider.call('/rest/v1/rpc/custom_u_hr_115',rec['token'],{'payload':{'op':'device_check','digest':value}},limit=100000))
    except failure:raise
    except (ValueError,TypeError):raise failure('DEVICE_CHECK_UNAVAILABLE',503) from None
    if result.get('approved') is not True:raise failure('APPROVED_COMPUTER_REQUIRED',403)
def ensure_cookie(response):
    if digest():return
    value=secrets.token_urlsafe(48)
    response.set_cookie(COOKIE,value,secure=True,httponly=True,samesite='Strict',max_age=31536000,path='/')
