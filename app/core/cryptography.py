import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

logger = logging.getLogger(__name__)

# Fernet tokens are URL-safe base64 and always begin with this version byte
# (0x80) once base64-encoded, i.e. the literal prefix "gAAAAA". We use it to
# tell a genuine ciphertext (which must decrypt or error) apart from legacy
# plaintext that predates encryption (which we still tolerate).
_FERNET_PREFIX = "gAAAAA"

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
    Decrypt a Fernet-encrypted string and return the plain text.

    Fail-closed for genuine ciphertext: if a value *looks* like a Fernet token
    (``gAAAAA`` prefix) but cannot be decrypted, that means the key is wrong,
    rotated, or the data is corrupt — we raise instead of silently returning
    the still-encrypted blob as if it were plaintext (the previous behaviour,
    which could hand a garbage "DB URL" to callers and mask key/tamper issues).

    Legacy plaintext that predates encryption (no Fernet prefix) is tolerated
    and returned unchanged, so this does not break rows written before
    encryption was introduced.
    """
    if not cipher_text:
        return cipher_text

    looks_encrypted = cipher_text.startswith(_FERNET_PREFIX)
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(cipher_text.encode())
        return decrypted.decode()
    except (InvalidToken, ValueError) as exc:
        if looks_encrypted:
            # Genuine ciphertext we could not decrypt — do NOT fall back to the
            # ciphertext. Surface it so the caller fails loudly.
            logger.error(
                "decrypt_string: failed to decrypt a Fernet token (wrong/rotated "
                "DATABASE_ENCRYPTION_KEY or corrupt data)."
            )
            raise
        # Not an encrypted value — legacy plaintext; return unchanged.
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
