"""Workspace backup container shared by 097/098; snapshot JSON carries its version."""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backup_codec import key_for, parse, passphrase_bytes
MAGIC=b'CUSTOMU-WORK-097\x00'
MAX_BYTES=20*1024*1024

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
