import os
import secrets
from pydantic_settings import BaseSettings
from functools import lru_cache

_DEFAULT_SECRET = "change-this-to-a-random-secret-key-at-least-32-chars"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://mikrocontrol:mikrocontrol_secret_2026@localhost:5432/mikrocontrol"
    REDIS_URL: str = ""
    SECRET_KEY: str = _DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DEBUG: bool = False
    # Orígenes permitidos para CORS (separados por coma). Por defecto solo el
    # frontend local. Configurable con la variable de entorno CORS_ORIGINS.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "MikroControl <alerts@mikrocontrol.local>"

    WIREGUARD_INTERFACE: str = "wg0"
    WIREGUARD_NETWORK: str = "10.10.0.0/24"

    ROUTEROS_DEFAULT_USERNAME: str = "admin"
    ROUTEROS_API_PORT: int = 8728
    ROUTEROS_API_SSL_PORT: int = 8729

    class Config:
        env_file = ".env"
        extra = "ignore"


def _resolve_secret_key(current: str) -> str:
    """Si SECRET_KEY sigue siendo el valor por defecto (o vacío), genera una
    clave aleatoria y la persiste para que los tokens JWT y los secretos
    cifrados (contraseñas de routers) sobrevivan reinicios.

    Intenta varias ubicaciones de persistencia, en orden:
      1. 'secret.key' en la raíz del backend (si el proceso puede escribir).
      2. '$HOME/.mikrocontrol_secret.key' (el usuario del servicio, p.ej.
         www-data, suele poder escribir en su HOME => persiste entre reinicios).
    Si ninguna es escribible, cae en una clave efímera (no persisten los tokens).
    """
    if current and current != _DEFAULT_SECRET:
        return current
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    home = os.environ.get("HOME") or "/var/www"
    candidates = [
        os.path.join(base_dir, "secret.key"),
        os.path.join(home, ".mikrocontrol_secret.key"),
    ]
    for key_path in candidates:
        try:
            if os.path.isfile(key_path):
                with open(key_path, "r", encoding="utf-8") as f:
                    saved = f.read().strip()
                if saved:
                    return saved
            generated = secrets.token_urlsafe(48)
            parent = os.path.dirname(key_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(generated)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            print(f"SECRET_KEY generada y guardada en {key_path}")
            return generated
        except OSError:
            continue
    # Último recurso: clave efímera (los tokens no sobreviven reinicios).
    return secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.SECRET_KEY = _resolve_secret_key(s.SECRET_KEY)
    return s
