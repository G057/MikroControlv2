from datetime import datetime, timedelta, timezone
from typing import Optional, List
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, never_expires: bool = False) -> str:
    to_encode = data.copy()
    if not never_expires:
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_permissions(user) -> List[str]:
    """Devuelve la lista de permisos del usuario. El rol 'admin' tiene acceso total."""
    from app.core.permissions import ALL_PERMISSIONS
    if user.role == "admin":
        return list(ALL_PERMISSIONS)
    from app.models.role import Role
    role = Role.__table__
    # Importar aquí para evitar ciclos
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        r = db.query(Role).filter(Role.name == user.role).first()
        if not r:
            return []
        return r.get_permissions()
    finally:
        db.close()


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.user import User

    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")
    if payload.get("tv", 0) != (user.token_version or 0):
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada, iniciá sesión nuevamente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(permission: str):
    async def checker(current_user=Depends(get_current_user)):
        if current_user.role == "admin":
            return current_user
        perms = get_user_permissions(current_user)
        if permission not in perms:
            raise HTTPException(status_code=403, detail=f"Permiso requerido: {permission}")
        return current_user
    return checker


def require_any_permission(*permissions: str):
    async def checker(current_user=Depends(get_current_user)):
        if current_user.role == "admin":
            return current_user
        perms = get_user_permissions(current_user)
        if not any(p in perms for p in permissions):
            raise HTTPException(status_code=403, detail=f"Permiso requerido: uno de {list(permissions)}")
        return current_user
    return checker
