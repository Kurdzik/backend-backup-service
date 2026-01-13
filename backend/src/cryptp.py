import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def _derive_key(password: str, salt: bytes) -> bytes:
    """
    Derives a 32-byte (256-bit) key from the password using PBKDF2.
    This makes it computationally expensive for attackers to guess the key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode('utf-8'))

def encrypt_str(plaintext: str) -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    salt = os.urandom(16)
    nonce = os.urandom(12)

    key = _derive_key(secret, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)

    packed_data = salt + nonce + ciphertext
    
    return base64.urlsafe_b64encode(packed_data).decode('utf-8')

def decrypt_str(encrypted_token: str) -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    try:
        data = base64.urlsafe_b64decode(encrypted_token)
        
        salt = data[:16]
        nonce = data[16:28]
        ciphertext = data[28:]

        key = _derive_key(secret, salt)

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
        
    except Exception as e:
        raise ValueError("Decryption failed. Invalid Key or Data Tampered.") from e

