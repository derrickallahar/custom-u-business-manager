"""Encrypted per-job artwork bundle; separate from the workspace metadata backup."""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backup_codec import key_for,passphrase_bytes
MAGIC=b'CUSTOMU-ART-104\x00'
MAX_BYTES=45000000

def encrypt(raw,password):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError('ARTWORK_BACKUP_SIZE')
    salt=os.urandom(16);nonce=os.urandom(12);head=MAGIC+salt+nonce
    return head+AESGCM(key_for(password,salt)).encrypt(nonce,raw,head)

def decrypt(blob,password):
    size=len(MAGIC)+28
    if not isinstance(blob,bytes) or not size+16<=len(blob)<=MAX_BYTES+size+16 or not blob.startswith(MAGIC):raise ValueError('INVALID_ARTWORK_BACKUP')
    try:return AESGCM(key_for(password,blob[len(MAGIC):len(MAGIC)+16])).decrypt(blob[len(MAGIC)+16:size],blob[size:],blob[:size])
    except Exception:raise ValueError('WRONG_PASSPHRASE_OR_DAMAGED_BACKUP') from None
