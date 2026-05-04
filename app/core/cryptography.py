import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings

def _get_fernet() -> Fernet:
    """
    Derive a 32-byte key from settings.DATABASE_ENCRYPTION_KEY and return a Fernet instance.
    """
    key_source = settings.DATABASE_ENCRYPTION_KEY
    # Use SHA-256 to derive a 32-byte key
    key_hash = hashlib.sha256(key_source.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)

def encrypt_string(plain_text: str) -> str:
    """
    Encrypt a plain text string and return the base64 encoded cipher text.
    """
    if not plain_text:
        return plain_text
    
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plain_text.encode())
    return encrypted.decode()

def decrypt_string(cipher_text: str) -> str:
    """
    Decrypt a base64 encoded cipher text and return the plain text.
    """
    if not cipher_text:
        return cipher_text

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(cipher_text.encode())
        return decrypted.decode()
    except Exception:
        # If decryption fails (e.g. if it was already plain text or key changed),
        # return as is or handle accordingly. For safety in transition, return as is.
        return cipher_text


def encrypt_bytes(plain_bytes: bytes) -> bytes:
    """
    Encrypt arbitrary binary content (such as a backup dump) with the
    platform encryption key. Returns the Fernet token as bytes.
    """
    if plain_bytes is None:
        return plain_bytes
    return _get_fernet().encrypt(plain_bytes)


def decrypt_bytes(cipher_bytes: bytes) -> bytes:
    """
    Decrypt a Fernet-encrypted byte payload produced by :func:`encrypt_bytes`.
    Raises :class:`cryptography.fernet.InvalidToken` if the payload is
    corrupt or was encrypted with a different key.
    """
    if cipher_bytes is None:
        return cipher_bytes
    return _get_fernet().decrypt(cipher_bytes)
