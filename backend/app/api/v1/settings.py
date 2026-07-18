import os
import smtplib
import json
import subprocess
import shutil
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
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
from app.core.backup_utils import BACKUP_DIR, validate_backup_schedule

router = APIRouter()

MANAGED_SERVICES = {
    "mikrocontrol": "Backend MikroControl",
    "nginx": "Nginx",
    "postgresql": "PostgreSQL",
}

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
    "event_info_retention_days": "30",
    "unmatched_syslog_retention_days": "14",
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
    "syslog_queue_max_size": "500",
    "syslog_worker_count": "1",
    "health_failures_to_offline": "3",
    "health_successes_to_online": "2",
    "popup_exclusion_filters": "",
    "telegram_exclusion_filters": "",
    "event_classification_rules": "[]",
    "alert_recovery_rules": "[]",
    "filter_gallery": "[]",
    "storage_exclusion_filters": "",
    "event_consolidation_minutes": "5",
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
    syslog_queue_max_size: Optional[str] = None
    syslog_worker_count: Optional[str] = None
    health_failures_to_offline: Optional[str] = None
    health_successes_to_online: Optional[str] = None
    popup_exclusion_filters: Optional[str] = None
    telegram_exclusion_filters: Optional[str] = None
    event_classification_rules: Optional[str] = None
    storage_exclusion_filters: Optional[str] = None
    event_consolidation_minutes: Optional[str] = None
    event_info_retention_days: Optional[str] = None
    unmatched_syslog_retention_days: Optional[str] = None


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


@router.get("/services")
def get_services(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:view")),
):
    def _memory():
        values = {}
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    key, value = line.split(":", 1)
                    values[key] = int(value.strip().split()[0]) * 1024
        except OSError:
            return {"total": 0, "available": 0, "used": 0, "percent": 0}
        total, available = values.get("MemTotal", 0), values.get("MemAvailable", 0)
        used = max(0, total - available)
        return {"total": total, "available": available, "used": used, "percent": round((used / total * 100) if total else 0, 1)}

    services = []
    for name, label in MANAGED_SERVICES.items():
        result = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=3, check=False)
        services.append({"name": name, "label": label, "status": result.stdout.strip() or "unknown", "canRestart": name in ("mikrocontrol", "nginx", "postgresql")})
    disk = shutil.disk_usage("/")
    try:
        database_size = db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0
        database_connections = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")).scalar() or 0
    except Exception:
        database_size, database_connections = 0, 0
    backup_size = 0
    for root, _, files in os.walk(BACKUP_DIR):
        for filename in files:
            try:
                backup_size += os.path.getsize(os.path.join(root, filename))
            except OSError:
                pass
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime_seconds = int(float(handle.read().split()[0]))
    except OSError:
        uptime_seconds = 0
    return {"services": services, "resources": {
        "load": [round(value, 2) for value in os.getloadavg()],
        "cpuCount": os.cpu_count() or 1, "memory": _memory(),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "percent": round(disk.used / disk.total * 100, 1)},
        "database": {"size": database_size, "connections": database_connections},
        "backupsSize": backup_size, "uptimeSeconds": uptime_seconds,
    }}


@router.post("/services/{service_name}/restart")
def restart_service(
    service_name: str,
    current_user: User = Depends(require_permission("settings:edit")),
):
    if service_name not in MANAGED_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio no administrable")
    try:
        # The systemd policy grants www-data only these exact restart commands.
        result = subprocess.run(["sudo", "-n", "/bin/systemctl", "restart", service_name], capture_output=True, text=True, timeout=15, check=False)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="El reinicio excedió el tiempo máximo")
    if result.returncode:
        raise HTTPException(status_code=503, detail="No se pudo reiniciar. Verificá la política sudoers de MikroControl.")
    return {"detail": f"{MANAGED_SERVICES[service_name]} reiniciado"}


@router.get("/storage-usage")
def storage_usage(db: Session = Depends(get_db), _: User = Depends(require_permission("settings:view"))):
    tables = db.execute(text("SELECT relname, pg_total_relation_size(relid), n_live_tup FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC")).all()
    return {"tables": [{"name": row[0], "bytes": int(row[1]), "rows": int(row[2] or 0)} for row in tables], "policies": {
        "infoDays": int(get_setting(db, "event_info_retention_days", "30")),
        "eventDays": int(get_setting(db, "event_retention_days", "90")),
        "trafficDays": int(get_setting(db, "traffic_retention_days", "7")),
        "unmatchedDays": int(get_setting(db, "unmatched_syslog_retention_days", "14")),
    }}


@router.post("/storage-usage/purge")
def purge_storage(db: Session = Depends(get_db), current_user: User = Depends(require_permission("settings:edit"))):
    from app.models.interface_traffic import InterfaceTraffic
    from app.models.monitoring import Notification, NotificationDelivery, UnmatchedSyslogMessage
    now = datetime.now(timezone.utc)
    def days(key, default):
        try: return max(1, int(get_setting(db, key, str(default))))
        except (ValueError, TypeError): return default
    info_cutoff = now - timedelta(days=days("event_info_retention_days", 30))
    event_cutoff = now - timedelta(days=days("event_retention_days", 90))
    traffic_cutoff = now - timedelta(days=days("traffic_retention_days", 7))
    unmatched_cutoff = now - timedelta(days=days("unmatched_syslog_retention_days", 14))
    old_notifications = db.query(Notification.id).filter(Notification.status == "acknowledged", Notification.acknowledged_at < event_cutoff)
    deleted = {
        "deliveries": db.query(NotificationDelivery).filter(NotificationDelivery.notification_id.in_(old_notifications)).delete(synchronize_session=False),
        "notifications": db.query(Notification).filter(Notification.id.in_(old_notifications)).delete(synchronize_session=False),
    }
    referenced_events = db.query(Notification.event_log_id).filter(Notification.event_log_id.isnot(None))
    deleted.update({
        "infoEvents": db.query(EventLog).filter(EventLog.severity == "info", EventLog.first_seen < info_cutoff, ~EventLog.id.in_(referenced_events)).delete(synchronize_session=False),
        "otherEvents": db.query(EventLog).filter(EventLog.severity != "info", EventLog.first_seen < event_cutoff, ~EventLog.id.in_(referenced_events)).delete(synchronize_session=False),
        "traffic": db.query(InterfaceTraffic).filter(InterfaceTraffic.timestamp < traffic_cutoff).delete(synchronize_session=False),
        "unmatched": db.query(UnmatchedSyslogMessage).filter(UnmatchedSyslogMessage.received_at < unmatched_cutoff).delete(synchronize_session=False),
    })
    log_audit(db, current_user.username, "purge", "storage", details=deleted, user_id=current_user.id)
    db.commit()
    return {"deleted": deleted}


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
    for days_key, time_key in (
        ("backup_schedule_days", "backup_schedule_time"),
        ("router_backup_schedule_days", "router_backup_schedule_time"),
    ):
        if days_key in updates or time_key in updates:
            current_days = get_setting(db, days_key, DEFAULTS[days_key])
            current_time = get_setting(db, time_key, DEFAULTS[time_key])
            try:
                days, schedule_time = validate_backup_schedule(
                    updates.get(days_key, current_days), updates.get(time_key, current_time)
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            updates[days_key] = days
            updates[time_key] = schedule_time
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
    if "syslog_enabled" in updates:
        from app.services.syslog_receiver import start_syslog_receiver, stop_syslog_receiver
        if updates["syslog_enabled"] == "true":
            start_syslog_receiver()
        else:
            stop_syslog_receiver()
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
            # Delivery/storage are global system behaviors, not per-viewer rules.
            "roles": [],
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


@router.get("/event-classification-rules")
def get_event_classification_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:edit")),
):
    from app.core.event_filter import load_json_setting
    return {"rules": load_json_setting(db, "event_classification_rules")}


@router.put("/event-classification-rules")
def update_event_classification_rules(
    data: dict,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="rules debe ser una lista")
    clean = []
    seen_ids = set()
    for rule in rules[:100]:
        if not isinstance(rule, dict):
            continue
        pattern = str(rule.get("pattern", "")).strip()
        event_type = str(rule.get("event_type", "")).strip().lower().replace(" ", "_")
        if not pattern or not event_type:
            continue
        clean.append({"id": str(rule.get("id", "")), "name": str(rule.get("name", ""))[:80],
                      "pattern": pattern[:300], "field": rule.get("field") if rule.get("field") in ("message", "topics", "any") else "message",
                      "mode": rule.get("mode") if rule.get("mode") in ("contains", "wildcard") else "contains",
                      "event_type": event_type[:80], "severity": rule.get("severity") if rule.get("severity") in ("critical", "warning", "info") else "warning",
                      "enabled": bool(rule.get("enabled", True))})
    _set(db, "event_classification_rules", json.dumps(clean))
    log_audit(db, current_user.username, "update", "settings", details={"event_classification_rules": len(clean)}, user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return {"rules": clean}


def _clean_recovery_pattern(value: dict) -> dict | None:
    if not isinstance(value, dict):
        return None
    pattern = str(value.get("pattern", "")).strip()
    if not pattern:
        return None
    return {
        "id": str(value.get("id", ""))[:100],
        "name": str(value.get("name", ""))[:80],
        "pattern": pattern[:300],
        "mode": value.get("mode") if value.get("mode") in ("contains", "wildcard", "regex") else "contains",
        "field": value.get("field") if value.get("field") in ("message", "topics", "any") else "message",
        "enabled": True,
    }


@router.get("/alert-recovery-rules")
def get_alert_recovery_rules(db: Session = Depends(get_db), _: User = Depends(require_permission("settings:edit"))):
    from app.core.event_filter import load_json_setting
    return {"rules": load_json_setting(db, "alert_recovery_rules")}


@router.put("/alert-recovery-rules")
def update_alert_recovery_rules(data: dict, req: Request, db: Session = Depends(get_db), current_user: User = Depends(require_permission("settings:edit"))):
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="rules debe ser una lista")
    clean = []
    for rule in rules[:100]:
        if not isinstance(rule, dict):
            continue
        opening, recovery = _clean_recovery_pattern(rule.get("opening")), _clean_recovery_pattern(rule.get("recovery"))
        if not opening or not recovery:
            raise HTTPException(status_code=400, detail="Cada regla requiere evento de apertura y recuperación")
        rule_id = str(rule.get("id", "")).strip()[:100]
        if not rule_id or rule_id in seen_ids:
            raise HTTPException(status_code=400, detail="Cada regla de recuperación requiere un ID único")
        if opening["pattern"].lower() == recovery["pattern"].lower() and opening["field"] == recovery["field"]:
            raise HTTPException(status_code=400, detail="Apertura y recuperación no pueden usar el mismo patrón")
        try:
            recovery_window = min(86400, max(1, int(rule.get("recovery_window_seconds", 300) or 300)))
            delay_seconds = min(86400, max(0, int(rule.get("delay_seconds", 0) or 0)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Los tiempos de recuperación deben ser números enteros")
        seen_ids.add(rule_id)
        clean.append({
            "id": rule_id,
            "name": str(rule.get("name", ""))[:80] or "Recuperación automática",
            "enabled": bool(rule.get("enabled", True)),
            "opening": opening,
            "recovery": recovery,
            "severity": rule.get("severity") if rule.get("severity") in ("warning", "critical") else "warning",
            "recovery_window_seconds": recovery_window,
            "delay_notification": bool(rule.get("delay_notification", False)),
            "delay_seconds": delay_seconds,
            "force_recovery_report": bool(rule.get("force_recovery_report", False)),
            "resolution_comment": str(rule.get("resolution_comment", "Resuelta automáticamente al detectar recuperación."))[:500],
        })
    _set(db, "alert_recovery_rules", json.dumps(clean))
    log_audit(db, current_user.username, "update", "settings", details={"alert_recovery_rules": len(clean)}, user_id=current_user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return {"rules": clean}


@router.get("/filter-gallery")
def get_filter_gallery(db: Session = Depends(get_db), _: User = Depends(require_permission("events:view"))):
    from app.core.event_filter import load_json_setting
    return {"filters": load_json_setting(db, "filter_gallery")}


@router.put("/filter-gallery")
def update_filter_gallery(data: dict, req: Request, db: Session = Depends(get_db), current_user: User = Depends(require_permission("settings:edit"))):
    return _save_filter_setting(db, "filter_gallery", data, current_user, req)


@router.get("/storage-filters")
def get_storage_filters(db: Session = Depends(get_db), _: User = Depends(require_permission("settings:edit"))):
    from app.core.event_filter import load_storage_filters
    return {"filters": load_storage_filters(db)}


@router.put("/storage-filters")
def update_storage_filters(data: dict, req: Request, db: Session = Depends(get_db), current_user: User = Depends(require_permission("settings:edit"))):
    return _save_filter_setting(db, "storage_exclusion_filters", data, current_user, req)
