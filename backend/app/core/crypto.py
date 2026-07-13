"""Cifrado simétrico para secretos en reposo (contraseñas de routers).

Usa Fernet (AES-128-CBC + HMAC) con una clave derivada de la SECRET_KEY
efectiva de la aplicación. Los valores cifrados se almacenan con el prefijo
'enc:' para poder distinguir valores legacy en texto plano y migrarlos.
"""
import base64, logging
import hashlib
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX = "enc:"


@lru_cache
def _fernet() -> Fernet:
    from app.core.config import get_settings
    secret = get_settings().SECRET_KEY.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def is_encrypted(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith(_PREFIX)


def encrypt_secret(plain: str) -> str:
    """Cifra un secreto en texto plano y devuelve una cadena con prefijo 'enc:'."""
    if plain is None or plain == "":
        return ""
    token = _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return _PREFIX + token


def decrypt_secret(stored: str) -> str:
    """Descifra un secreto. Si viene en texto plano (legacy, sin prefijo) lo
    devuelve tal cual para mantener compatibilidad hasta la migración."""
    if not stored:
        return ""
    if not is_encrypted(stored):
        return stored  # legacy plaintext
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.warning("decrypt_secret: no se pudo descifrar (token inválido): %s", e)
        return ""
