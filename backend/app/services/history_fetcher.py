import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from app.core.database import SessionLocal
from app.models.router import Router
from app.models.router_history import RouterHistory
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_history_thread = None
_stop_event = threading.Event()
_last_purge = 0.0
_PURGE_INTERVAL = 3600


def _purge_old_history(db):
    """Acota el crecimiento de router_history según history_retention_days."""
    global _last_purge
    now = time.time()
    if now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    try:
        from app.api.v1.settings import get_setting
        days = int(get_setting(db, "history_retention_days", "90") or "90")
        if days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = db.query(RouterHistory).filter(RouterHistory.first_seen < cutoff).delete(synchronize_session=False)
        db.commit()
        if deleted:
            logger.info(f"Retención: {deleted} registros de historial anteriores a {days} días eliminados")
    except Exception as e:
        logger.error(f"Error purgando historial antiguo: {e}")
        db.rollback()


def _create_alert(db, router_id, alert_type, severity, title, message):
    from app.api.v1.settings import get_setting
    if get_setting(db, "history_alerts_enabled", "true") != "true":
        return

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

    from app.api.v1.settings import notify
    icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "ℹ️"
    tg_msg = f"{icon} <b>{title}</b>\n{message}"
    notify(title, message, tg_msg, severity)


def _fetch_all_history():
    db = SessionLocal()
    try:
        routers = db.query(Router).filter(Router.is_online == True).all()
        for router in routers:
            try:
                _fetch_router_history(db, router)
            except Exception as e:
                logger.warning(f"History fetch failed for {router.name}: {e}")
                # History collection is not an availability probe. Health check owns state changes.
                logger.warning("History fetch failed for %s without changing connectivity", router.name)
        db.commit()
        _purge_old_history(db)
    except Exception as e:
        logger.error(f"Error in history fetcher: {e}")
        db.rollback()
    finally:
        db.close()


def _fetch_router_history(db, router):
    from app.services.routeros_service import _get_connection
    conn = _get_connection(router)
    conn.connect()
    try:
        entries = conn.command("/system/history/print")
        if not entries:
            return
        for entry in entries:
            ros_id = entry.get(".id", "")
            if not ros_id:
                continue
            existing = db.query(RouterHistory).filter(
                RouterHistory.router_id == router.id,
                RouterHistory.ros_id == ros_id,
            ).first()
            if existing:
                continue
            history = RouterHistory(
                router_id=router.id,
                router_name=router.name,
                ros_id=ros_id,
                action=entry.get("action", ""),
                redo=entry.get("redo", "").replace("\r\n", "\n").strip(),
                undo=entry.get("undo", "").replace("\r\n", "\n").strip() or None,
                by_user=entry.get("by", ""),
                policy=entry.get("policy", ""),
                ros_time=entry.get("time", ""),
                trace=entry.get("trace", ""),
                undoable=entry.get("undoable", ""),
            )
            db.add(history)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _run_loop():
    while not _stop_event.is_set():
        try:
            _fetch_all_history()
        except Exception as e:
            logger.error(f"History fetcher loop error: {e}")
        from app.api.v1.settings import get_interval
        interval = get_interval("history_fetch_interval", 300)
        _stop_event.wait(interval)


def start_history_fetcher():
    global _history_thread
    if _history_thread and _history_thread.is_alive():
        return
    _stop_event.clear()
    _history_thread = threading.Thread(target=_run_loop, daemon=True, name="history-fetcher")
    _history_thread.start()
    logger.info("Router history fetcher started (interval: 5 min)")


def stop_history_fetcher():
    _stop_event.set()
