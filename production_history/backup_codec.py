"""094 authenticated encrypted container; fixed KDF parameters and bounded input."""
import hashlib, json, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
MAGIC=b'CUSTOMU-CRM-094\x00'
MAX_BYTES=20*1024*1024
ITERATIONS=600000

def passphrase_bytes(value):
    if not isinstance(value,str) or not 12<=len(value)<=256:
        raise ValueError('PASSPHRASE_LENGTH')
    return value.encode('utf-8')

def key_for(password,salt):
    return hashlib.pbkdf2_hmac('sha256',passphrase_bytes(password),salt,ITERATIONS,dklen=32)

def encrypt(raw,password):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError('BACKUP_SIZE')
    salt=os.urandom(16);nonce=os.urandom(12);header=MAGIC+salt+nonce
    return header+AESGCM(key_for(password,salt)).encrypt(nonce,raw,header)

def decrypt(blob,password):
    size=len(MAGIC)+28
    if not isinstance(blob,bytes) or not size+16<=len(blob)<=MAX_BYTES+size+16 or not blob.startswith(MAGIC):raise ValueError('INVALID_BACKUP_FILE')
    salt=blob[len(MAGIC):len(MAGIC)+16];nonce=blob[len(MAGIC)+16:size]
    try:return AESGCM(key_for(password,salt)).decrypt(nonce,blob[size:],blob[:size])
    except Exception:raise ValueError('WRONG_PASSPHRASE_OR_DAMAGED_BACKUP') from None

def no_duplicates(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:raise ValueError('DUPLICATE_JSON_KEY')
        obj[key]=value
    return obj

def parse(raw):
    if len(raw)>MAX_BYTES:raise ValueError('BACKUP_SIZE')
    return json.loads(raw,object_pairs_hook=no_duplicates,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('INVALID_JSON_NUMBER')))
