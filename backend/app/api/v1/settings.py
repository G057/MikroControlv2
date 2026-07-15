import os
import smtplib
import json
import subprocess
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse
from app.core.database import get_db, engine, Base, SessionLocal, settings as db_settings
from app.core.datetime_utils import utc_iso
from app.core.security import require_permission, get_password_hash
from app.core.crypto import encrypt_secret, decrypt_secret, is_encrypted
from app.models.user import User
from app.models.settings import SystemSetting
from app.models.router import Router
from app.models.backup import Backup
from app.models.alert import Alert
from app.models.event_log import EventLog
from app.models.router_history import RouterHistory
from app.models.audit import AuditLog
from app.utils.audit import log_audit

router = APIRouter()

DEFAULTS = {
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_tls": "true",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notify_router_offline": "true",
    "notify_router_online": "true",
    "notify_critical_alert": "true",
    "notify_warning_alert": "true",
    "notify_repeat_critical": "true",
    "notify_repeat_warning": "true",
    "notify_backup_complete": "false",
    "notify_high_cpu": "false",
    "notify_high_temp": "false",
    "notify_email_enabled": "false",
    "notify_telegram_enabled": "false",
    "health_check_interval": "60",
    "log_fetch_interval": "60",
    "history_fetch_interval": "120",
    "traffic_fetch_interval": "60",
    "health_alerts_enabled": "true",
    "log_alerts_enabled": "true",
    "history_alerts_enabled": "true",
    "event_retention_days": "90",
    "history_retention_days": "90",
    "traffic_retention_days": "7",
    "backup_interval_hours": "6",
    "backup_schedule_days": "",
    "backup_schedule_time": "03:00",
    "router_backup_interval_hours": "6",
    "router_backup_schedule_days": "",
    "router_backup_schedule_time": "03:00",
    "router_backup_type": "export",
    "router_backup_retention_days": "30",
    "router_backup_retention_count": "60",
    "syslog_enabled": "false",
    "syslog_port": "5140",
    "popup_exclusion_filters": "",
    "telegram_exclusion_filters": "",
}

# Claves cuyo valor es un secreto: se cifran en reposo y se enmascaran al leer.
SENSITIVE_KEYS = {"smtp_password", "telegram_bot_token"}
MASK = "********"


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        return default
    if key in SENSITIVE_KEYS:
        return decrypt_secret(row.value)
    return row.value


def get_interval(key: str, default: int) -> int:
    db = SessionLocal()
    try:
        val = get_setting(db, key, str(default))
        return max(30, int(val))
    except (ValueError, TypeError):
        return default
    finally:
        db.close()


def _get_all(db: Session) -> dict:
    """Uso interno: devuelve valores reales (secretos descifrados)."""
    rows = db.query(SystemSetting).all()
    settings = {**DEFAULTS}
    for r in rows:
        if r.key in SENSITIVE_KEYS:
            settings[r.key] = decrypt_secret(r.value)
        else:
            settings[r.key] = r.value
    return settings


def _get_all_masked(db: Session) -> dict:
    """Para respuestas de la API: enmascara los secretos configurados."""
    settings = _get_all(db)
    for k in SENSITIVE_KEYS:
        settings[k] = MASK if settings.get(k) else ""
    return settings


def _set(db: Session, key: str, value: str):
    if key in SENSITIVE_KEYS and value and not is_encrypted(value):
        value = encrypt_secret(value)
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


class SettingsUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_router_offline: Optional[str] = None
    notify_router_online: Optional[str] = None
    notify_critical_alert: Optional[str] = None
    notify_warning_alert: Optional[str] = None
    notify_repeat_critical: Optional[str] = None
    notify_repeat_warning: Optional[str] = None
    notify_backup_complete: Optional[str] = None
    notify_high_cpu: Optional[str] = None
    notify_high_temp: Optional[str] = None
    notify_email_enabled: Optional[str] = None
    notify_telegram_enabled: Optional[str] = None
    health_check_interval: Optional[str] = None
    log_fetch_interval: Optional[str] = None
    history_fetch_interval: Optional[str] = None
    traffic_fetch_interval: Optional[str] = None
    health_alerts_enabled: Optional[str] = None
    log_alerts_enabled: Optional[str] = None
    history_alerts_enabled: Optional[str] = None
    event_retention_days: Optional[str] = None
    history_retention_days: Optional[str] = None
    traffic_retention_days: Optional[str] = None
    backup_interval_hours: Optional[str] = None
    backup_schedule_days: Optional[str] = None
    backup_schedule_time: Optional[str] = None
    router_backup_interval_hours: Optional[str] = None
    router_backup_schedule_days: Optional[str] = None
    router_backup_schedule_time: Optional[str] = None
    router_backup_type: Optional[str] = None
    router_backup_retention_days: Optional[str] = None
    router_backup_retention_count: Optional[str] = None
    syslog_enabled: Optional[str] = None
    syslog_port: Optional[str] = None
    popup_exclusion_filters: Optional[str] = None
    telegram_exclusion_filters: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: str = "tecnico_n1"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    return _get_all_masked(db)


@router.put("/")
def update_settings(
    data: SettingsUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is None:
            continue
        # No sobrescribir un secreto con el valor enmascarado devuelto por GET.
        if key in SENSITIVE_KEYS and value == MASK:
            continue
        _set(db, key, value)
    log_audit(db, current_user.username, "update", "settings",
              details={"fields": list(updates.keys())},
              user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return _get_all_masked(db)


@router.post("/test-email")
def test_email(
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    settings = _get_all(db)
    host = settings.get("smtp_host", "")
    port = int(settings.get("smtp_port", "587") or "587")
    user = settings.get("smtp_user", "")
    password = settings.get("smtp_password", "")
    from_addr = settings.get("smtp_from", "") or user
    use_tls = settings.get("smtp_tls", "true") == "true"

    if not host:
        raise HTTPException(status_code=400, detail="SMTP no configurado")

    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = user
        msg["Subject"] = "MikroControl - Test de correo"
        msg.attach(MIMEText(
            "Este es un correo de prueba de MikroControl.\n\nSi lo estás leyendo, la configuración SMTP funciona correctamente.",
            "plain", "utf-8"
        ))
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=10)
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, [user], msg.as_string())
        server.quit()
        log_audit(db, current_user.username, "test_email", "settings",
                  user_id=current_user.id, ip_address=req.client.host if req.client else None)
        db.commit()
        return {"success": True, "message": f"Correo enviado a {user}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al enviar: {str(e)}")


@router.post("/test-telegram")
def test_telegram(
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    settings = _get_all(db)
    token = settings.get("telegram_bot_token", "")
    chat_id = settings.get("telegram_chat_id", "")

    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram no configurado")

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": "MikroControl - Test de notificación\n\nSi ves este mensaje, la configuración de Telegram funciona correctamente.",
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            log_audit(db, current_user.username, "test_telegram", "settings",
                      user_id=current_user.id, ip_address=req.client.host if req.client else None)
            db.commit()
            return {"success": True, "message": "Mensaje enviado a Telegram"}
        else:
            detail = resp.json().get("description", resp.text)
            raise HTTPException(status_code=400, detail=f"Error de Telegram: {detail}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Error de conexión: {str(e)}")


def send_email(settings: dict, subject: str, body: str):
    host = settings.get("smtp_host", "")
    if not host or settings.get("notify_email_enabled") != "true":
        return
    port = int(settings.get("smtp_port", "587") or "587")
    user = settings.get("smtp_user", "")
    password = settings.get("smtp_password", "")
    from_addr = settings.get("smtp_from", "") or user
    use_tls = settings.get("smtp_tls", "true") == "true"
    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = user
        msg["Subject"] = f"[MikroControl] {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=10)
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, [user], msg.as_string())
        server.quit()
    except Exception:
        pass


def send_telegram(settings: dict, message: str):
    token = settings.get("telegram_bot_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    if not token or not chat_id or settings.get("notify_telegram_enabled") != "true":
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        httpx.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


def notify(subject: str, body: str, telegram_msg: str = None, severity: str = None, message: str = "", topics: str = ""):
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        settings = _get_all(db)
        send_email(settings, subject, body)
        if severity == "critical" and settings.get("notify_critical_alert", "true") != "true":
            return
        if severity == "warning" and settings.get("notify_warning_alert", "false") != "true":
            return
        # Telegram exclusion filters — saltear para health critical (router_offline)
        if message and severity in ("critical", "warning"):
            from app.core.event_filter import load_telegram_filters, is_event_excluded
            tg_filters = load_telegram_filters(db)
            if tg_filters and is_event_excluded(message, topics, tg_filters):
                if topics.startswith("health,") and severity == "critical":
                    pass  # router_offline siempre notifica
                else:
                    return  # Suprimido por filtro
        send_telegram(settings, telegram_msg or body)
    except Exception:
        pass
    finally:
        db.close()


@router.get("/backup/download")
def download_system_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    backup_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_path = os.path.join(backup_dir, f"mikrocontrol_{ts}.dump")

    p = urlparse(db_settings.DATABASE_URL)
    conn = {
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "user": p.username or "postgres",
        "password": p.password or "",
        "dbname": p.path.lstrip("/") or "mikrocontrol",
    }
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    try:
        subprocess.run(
            ["pg_dump", "-h", conn["host"], "-p", conn["port"], "-U", conn["user"],
             "-F", "c", "-f", db_path, conn["dbname"]],
            env=env, check=True, capture_output=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="pg_dump no encontrado. Instalá PostgreSQL client.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error al generar backup: {e.stderr.decode(errors='ignore')[:300]}")

    log_audit(db, current_user.username, "backup", "system",
              details={"file": os.path.basename(db_path)},
              user_id=current_user.id)
    db.commit()
    return FileResponse(
        path=db_path,
        filename=f"mikrocontrol_backup_{ts}.dump",
        media_type="application/octet-stream",
        background=None,
    )


@router.post("/backup/restore")
def restore_system_backup(
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    log_audit(db, current_user.username, "restore", "system",
              user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return {"detail": "Usá el endpoint POST /settings/backup/restore/{filename} (o la seccion Backups) para restaurar un respaldo de PostgreSQL."}


@router.get("/event-filters")
def get_event_filters(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:edit")),
):
    from app.core.event_filter import load_exclusion_filters
    return {"filters": load_exclusion_filters(db)}


@router.put("/event-filters")
def update_event_filters(
    data: dict,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    filters = data.get("filters", [])
    if not isinstance(filters, list):
        raise HTTPException(status_code=400, detail="filters debe ser una lista")
    clean = []
    for f in filters:
        if not isinstance(f, dict):
            continue
        clean.append({
            "id": str(f.get("id", "")),
            "name": str(f.get("name", ""))[:80],
            "pattern": str(f.get("pattern", "")),
            "mode": f.get("mode", "contains") if f.get("mode") in ("contains", "wildcard", "regex") else "contains",
            "field": f.get("field", "message") if f.get("field") in ("message", "topics", "any") else "message",
            "enabled": bool(f.get("enabled", True)),
            "roles": [str(r) for r in (f.get("roles") or []) if isinstance(r, str)][:50],
        })
    _set(db, "event_exclusion_filters", json.dumps(clean))
    log_audit(db, current_user.username, "update", "settings",
              details={"event_filters": len(clean)},
              user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return {"filters": clean}


def _save_filter_setting(db: Session, key: str, data: dict, current_user: User, req: Request):
    """Valida y guarda una lista de reglas de filtro en una setting."""
    filters = data.get("filters", [])
    if not isinstance(filters, list):
        raise HTTPException(status_code=400, detail="filters debe ser una lista")
    clean = []
    for f in filters:
        if not isinstance(f, dict):
            continue
        clean.append({
            "id": str(f.get("id", "")),
            "name": str(f.get("name", ""))[:80],
            "pattern": str(f.get("pattern", "")),
            "mode": f.get("mode", "contains") if f.get("mode") in ("contains", "wildcard", "regex") else "contains",
            "field": f.get("field", "message") if f.get("field") in ("message", "topics", "any") else "message",
            "enabled": bool(f.get("enabled", True)),
            "roles": [str(r) for r in (f.get("roles") or []) if isinstance(r, str)][:50],
        })
    _set(db, key, json.dumps(clean))
    log_audit(db, current_user.username, "update", "settings",
              details={key: len(clean)},
              user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return {"filters": clean}


@router.get("/popup-filters")
def get_popup_filters(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:edit")),
):
    from app.core.event_filter import load_popup_filters
    return {"filters": load_popup_filters(db)}


@router.put("/popup-filters")
def update_popup_filters(
    data: dict,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    return _save_filter_setting(db, "popup_exclusion_filters", data, current_user, req)


@router.get("/telegram-filters")
def get_telegram_filters(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:edit")),
):
    from app.core.event_filter import load_telegram_filters
    return {"filters": load_telegram_filters(db)}


@router.put("/telegram-filters")
def update_telegram_filters(
    data: dict,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    return _save_filter_setting(db, "telegram_exclusion_filters", data, current_user, req)


@router.get("/users")
def list_operators(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    users = db.query(User).order_by(User.username).all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
            "last_login": utc_iso(u.last_login),
        }
        for u in users
    ]


@router.post("/users")
def create_operator(
    data: UserCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username ya existe")
    from app.core.user_ops import validate_password_strength, assert_can_assign_role
    validate_password_strength(data.password)
    assert_can_assign_role(current_user, data.role, db)
    user = User(
        username=data.username, email=data.email, full_name=data.full_name,
        hashed_password=get_password_hash(data.password), role=data.role, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(db, current_user.username, "create", "user",
              user.id, user.username, {"role": user.role},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return {"id": user.id, "username": user.username, "email": user.email,
            "full_name": user.full_name, "role": user.role, "is_active": user.is_active}


@router.put("/users/{user_id}")
def update_operator(
    user_id: int,
    data: UserUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    from app.core.user_ops import validate_password_strength, assert_can_assign_role

    def _last_admin(u):
        return u.role == "admin" and db.query(User).filter(User.role == "admin").count() <= 1

    if data.role is not None and data.role != user.role:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No podés cambiar tu propio rol")
        assert_can_assign_role(current_user, data.role, db)
        if _last_admin(user):
            raise HTTPException(status_code=400, detail="No podés cambiar el rol del último administrador")
    if data.is_active is False:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No podés desactivar tu propia cuenta")
        if _last_admin(user):
            raise HTTPException(status_code=400, detail="No podés desactivar al último administrador")
    if data.email is not None:
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        validate_password_strength(data.password)
        user.hashed_password = get_password_hash(data.password)
        user.token_version = (user.token_version or 0) + 1
    db.commit()
    log_audit(db, current_user.username, "update", "user",
              user.id, user.username, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.commit()
    return {"id": user.id, "username": user.username, "email": user.email,
            "full_name": user.full_name, "role": user.role, "is_active": user.is_active}


@router.delete("/users/{user_id}")
def delete_operator(
    user_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="No podés eliminarte a vos mismo")
    if user.role == "admin" and db.query(User).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=400, detail="No podés eliminar al último administrador")
    from app.core.user_ops import delete_user_record
    name = user.username
    log_audit(db, current_user.username, "delete", "user",
              user.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    delete_user_record(db, user)
    db.commit()
    return {"detail": "Usuario eliminado"}
