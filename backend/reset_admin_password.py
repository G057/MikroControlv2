from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
admin = db.query(User).filter(User.username == "admin").first()
if admin:
    admin.hashed_password = get_password_hash("admin123")
    db.commit()
    print("Contraseña de admin reseteada a: admin123")
else:
    print("No se encontró el usuario admin")
db.close()
