"""Workspace backup container shared by 097/098/099/100; snapshot JSON carries its version."""
import os,json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backup_codec import key_for, no_duplicates, passphrase_bytes
MAGIC=b'CUSTOMU-WORK-097\x00'
MAX_BYTES=80*1024*1024

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

def parse(raw):
    if len(raw)>MAX_BYTES:raise ValueError("BACKUP_SIZE")
    return json.loads(raw,object_pairs_hook=no_duplicates,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("INVALID_JSON_NUMBER")))
