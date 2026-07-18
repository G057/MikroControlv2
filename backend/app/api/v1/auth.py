import threading
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_current_user, get_user_permissions
from app.models.user import User
from app.models.monitoring import Notification
from app.schemas.user import LoginRequest, TokenResponse, UserResponse
from app.utils.audit import log_audit

router = APIRouter()

# Rate-limiting de login en memoria (por IP + usuario) para frenar fuerza bruta.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_LOCKOUT_SECONDS = 300
_login_attempts: dict[str, list[float]] = {}
_lockouts: dict[str, float] = {}
_attempts_lock = threading.Lock()


def _rate_limit_key(username: str, req: Request) -> str:
    ip = req.client.host if req.client else "unknown"
    return f"{ip}|{(username or '').lower()}"


def _check_lockout(key: str):
    now = time.time()
    with _attempts_lock:
        until = _lockouts.get(key)
        if until and until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Probá de nuevo en {int(until - now)} segundos.",
            )
        if until and until <= now:
            _lockouts.pop(key, None)
            _login_attempts.pop(key, None)


def _record_failure(key: str):
    now = time.time()
    with _attempts_lock:
        attempts = [t for t in _login_attempts.get(key, []) if now - t < _WINDOW_SECONDS]
        attempts.append(now)
        _login_attempts[key] = attempts
        if len(attempts) >= _MAX_ATTEMPTS:
            _lockouts[key] = now + _LOCKOUT_SECONDS
            _login_attempts.pop(key, None)


def _record_success(key: str):
    with _attempts_lock:
        _login_attempts.pop(key, None)
        _lockouts.pop(key, None)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    rl_key = _rate_limit_key(request.username, req)
    _check_lockout(rl_key)
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        _record_failure(rl_key)
        log_audit(db, request.username, "login_failed", "auth",
                  details={"reason": "credenciales incorrectas"},
                  ip_address=req.client.host if req.client else None)
        db.commit()
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user.is_active:
        log_audit(db, request.username, "login_blocked", "auth",
                  details={"reason": "usuario desactivado"},
                  ip_address=req.client.host if req.client else None)
        db.commit()
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    _record_success(rl_key)
    user.last_login = datetime.now(timezone.utc)
    log_audit(db, user.username, "login", "auth", user_id=user.id,
              ip_address=req.client.host if req.client else None)
    db.add(Notification(
        notification_type="app_login", severity="info", title="Inicio de sesión en MikroControl",
        message=f"{user.username} inició sesión desde {req.client.host if req.client else 'IP desconocida'}",
        popup_required=False, sound_required=False, telegram_required=False,
        deduplication_key=f"app_login:{user.id}:{datetime.now(timezone.utc).timestamp()}",
    ))
    db.commit()

    perms = get_user_permissions(user)
    timeout = user.session_timeout_minutes
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "perms": perms, "tv": user.token_version or 0},
        expires_delta=timedelta(minutes=timeout) if timeout and timeout > 0 else None,
        never_expires=timeout == 0,
    )
    user_data = UserResponse.model_validate(user).model_dump()
    user_data["permissions"] = perms
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(**user_data),
    )


@router.post("/logout")
def logout(
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.token_version = (current_user.token_version or 0) + 1
    log_audit(db, current_user.username, "logout", "auth", user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.commit()
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    perms = get_user_permissions(current_user)
    user_data = UserResponse.model_validate(current_user).model_dump()
    user_data["permissions"] = perms
    return UserResponse(**user_data)
