"""Re-encrypt persisted secrets after SECRET_KEY_PREVIOUS has been configured.

Run this as the service account while both keys are present in backend/.env.
It never prints plaintext values.
"""

from cryptography.fernet import InvalidToken

from app.api.v1.settings import SENSITIVE_KEYS
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, decrypt_secret_with_current_key, encrypt_secret, is_encrypted
from app.core.database import SessionLocal
from app.models.router import Router
from app.models.settings import SystemSetting


def _rotate(value: str) -> tuple[str, bool]:
    if not value:
        return value, False
    if not is_encrypted(value):
        return encrypt_secret(value), True
    try:
        decrypt_secret_with_current_key(value)
        return value, False
    except InvalidToken:
        plain = decrypt_secret(value)
        if not plain:
            raise RuntimeError("Se encontró un secreto que no puede descifrarse con ninguna clave configurada.")
        return encrypt_secret(plain), True


def main() -> None:
    settings = get_settings()
    if not settings.SECRET_KEY_PREVIOUS:
        raise SystemExit("Definí SECRET_KEY_PREVIOUS antes de ejecutar la rotación.")
    if settings.SECRET_KEY_PREVIOUS == settings.SECRET_KEY:
        raise SystemExit("SECRET_KEY_PREVIOUS debe ser diferente de SECRET_KEY.")

    db = SessionLocal()
    try:
        router_count = 0
        setting_count = 0
        for router in db.query(Router).all():
            rotated, changed = _rotate(router.api_password_encrypted or "")
            if changed:
                router.api_password_encrypted = rotated
                router_count += 1
        for setting in db.query(SystemSetting).filter(SystemSetting.key.in_(SENSITIVE_KEYS)).all():
            rotated, changed = _rotate(setting.value or "")
            if changed:
                setting.value = rotated
                setting_count += 1
        db.commit()
        print(f"Rotación completada: {router_count} credenciales de router y {setting_count} secretos de configuración.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
