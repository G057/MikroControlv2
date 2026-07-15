import hashlib
import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from app.core.database import SessionLocal
from app.models.router import Router
from app.models.event_log import EventLog
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_log_thread = None
_last_purge = 0.0
_PURGE_INTERVAL = 3600  # como máximo una purga por hora


def _purge_old_events(db):
    """Elimina eventos más antiguos que event_retention_days para acotar el
    crecimiento de la tabla event_logs. Corre como mucho una vez por hora."""
    global _last_purge
    now = time.time()
    if now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    try:
        from app.api.v1.settings import get_setting
        days = int(get_setting(db, "event_retention_days", "90") or "90")
        if days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = db.query(EventLog).filter(EventLog.first_seen < cutoff).delete(synchronize_session=False)
        db.commit()
        if deleted:
            logger.info(f"Retención: {deleted} eventos anteriores a {days} días eliminados")
    except Exception as e:
        logger.error(f"Error purgando eventos antiguos: {e}")
        db.rollback()

SEVERITY_MAP = {
    "critical": "critical",
    "error": "critical",
    "warning": "warning",
    "info": "info",
}


def _classify_severity(topics: str) -> str:
    for part in topics.lower().split(","):
        part = part.strip()
        if part in SEVERITY_MAP:
            return SEVERITY_MAP[part]
    return "info"


def _make_hash(router_id: int, ros_id: str, ros_time: str, topics: str, message: str) -> str:
    raw = f"{router_id}|{ros_id}|{ros_time}|{topics}|{message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _create_alert(db, router_id, alert_type, severity, title, message):
    existing = db.query(Alert).filter(
        Alert.router_id == router_id,
        Alert.alert_type == alert_type,
        Alert.is_resolved == False,
    ).first()
    if existing:
        return
    alert = Alert(
        router_id=router_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
    )
    db.add(alert)
    try:
        db.flush()
    except Exception:
        db.rollback()
        return

    from app.api.v1.settings import notify
    icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "ℹ️"
    tg_msg = f"{icon} <b>{title}</b>\n{message}"
    notify(title, message, tg_msg, severity)


def fetch_router_logs(db, router: Router) -> int:
    from app.services.routeros_service import _get_connection
    try:
        conn = _get_connection(router)
        conn.connect()
        logs = conn.command("/log/print")
        conn.close()
    except Exception as e:
        logger.warning(f"Error fetching logs from {router.name}: {e}")
        raise

    new_count = 0
    year = datetime.now().year

    for entry in logs:
        ros_id = entry.get(".id", "")
        ros_time = entry.get("time", "")
        topics = entry.get("topics", "")
        message = entry.get("message", "")

        if not message:
            continue

        severity = _classify_severity(topics)
        content_hash = _make_hash(router.id, ros_id, ros_time, topics, message)

        existing = db.query(EventLog).filter(EventLog.content_hash == content_hash).first()
        if existing:
            existing.last_seen = datetime.now(timezone.utc)
            continue

        log_time = ros_time
        try:
            if len(ros_time) == 8 and ros_time.count(":") == 2:
                log_time = f"{year}-{ros_time[:5]}"
            dt_obj = datetime.now(timezone.utc)
        except Exception:
            dt_obj = datetime.now(timezone.utc)

        event = EventLog(
            router_id=router.id,
            router_name=router.name,
            ros_time=ros_time,
            topics=topics,
            message=message,
            severity=severity,
            content_hash=content_hash,
        )
        db.add(event)
        try:
            db.flush()
            new_count += 1
        except Exception:
            db.rollback()
            continue

        if severity in ("warning", "critical") and _should_alert(db):
            alert_type = "log_warning" if severity == "warning" else "log_critical"
            _create_alert(db, router.id, alert_type, severity,
                          f"{router.name}: {severity}",
                          message[:200] if message else "Sin detalle")

    return new_count


def _should_alert(db) -> bool:
    from app.api.v1.settings import get_setting
    return get_setting(db, "log_alerts_enabled", "true") == "true"


def fetch_all_logs():
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        total_new = 0
        should_alert = _should_alert(db)
        for router in routers:
            try:
                n = fetch_router_logs(db, router)
                total_new += n
                if n > 0:
                    logger.info(f"[{router.name}] {n} new log entries")
            except Exception as e:
                logger.warning(f"Error fetching logs from {router.name}: {e}")
                if should_alert:
                    was_online = router.is_online
                    router.is_online = False
                    router.last_seen = datetime.now(timezone.utc)
                    if was_online:
                        _create_alert(db, router.id, "router_offline", "critical",
                                      f"{router.name} se desconectó",
                                      f"El router {router.name} dejó de responder (logs). Error: {e}")
            # Commit por router: transacción corta, libera el write-lock de SQLite
            # entre routers y evita retenerlo durante el I/O de red del siguiente.
            try:
                db.commit()
            except Exception as ce:
                logger.error(f"Error al persistir logs de {router.name}: {ce}")
                db.rollback()
        if total_new > 0:
            logger.info(f"Total new log entries: {total_new}")
        _purge_old_events(db)
    except Exception as e:
        logger.error(f"Error in log fetch: {e}")
        db.rollback()
    finally:
        db.close()


def _run_log_loop():
    while not _stop_event.is_set():
        try:
            fetch_all_logs()
        except Exception as e:
            logger.error(f"Log fetch loop error: {e}")
        from app.api.v1.settings import get_interval
        interval = get_interval("log_fetch_interval", 120)
        _stop_event.wait(interval)


def start_log_fetcher():
    global _log_thread
    if _log_thread and _log_thread.is_alive():
        return
    _stop_event.clear()
    _log_thread = threading.Thread(target=_run_log_loop, daemon=True, name="log-fetcher")
    _log_thread.start()
    logger.info("Log fetcher started (interval: 2 min)")


def stop_log_fetcher():
    _stop_event.set()
