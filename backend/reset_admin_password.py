import os

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

password = os.environ.get("MK_ADMIN_PASSWORD")
if not password:
    raise SystemExit("Definí MK_ADMIN_PASSWORD con una contraseña segura antes de ejecutar este script.")

db = SessionLocal()
admin = db.query(User).filter(User.username == "admin").first()
if admin:
    admin.hashed_password = get_password_hash(password)
    admin.token_version = (admin.token_version or 0) + 1
    db.commit()
    print("Contraseña de admin restablecida.")
else:
    print("No se encontró el usuario admin")
db.close()
