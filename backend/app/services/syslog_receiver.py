import logging
import re
import socket
import threading
import time
from datetime import datetime, timezone
from queue import Queue, Full as QueueFull

from app.core.database import SessionLocal
from app.models.router import Router
from app.models.event_log import EventLog
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_syslog_thread = None
_worker_thread = None
_stop_event = threading.Event()
_msg_queue = Queue(maxsize=500)  # buffer entre receptor y worker


def _classify_severity(topics: str) -> str:
    SEVERITY_MAP = {
        "critical": "critical",
        "error": "critical",
        "warning": "warning",
        "info": "info",
    }
    for part in topics.lower().split(","):
        part = part.strip()
        if part in SEVERITY_MAP:
            return SEVERITY_MAP[part]
    return "info"


def _make_hash(router_id: int, ros_id: str, ros_time: str, topics: str, message: str) -> str:
    import hashlib
    raw = f"{router_id}|syslog|{ros_time}|{topics}|{message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _find_router(db, hostname: str):
    for col in (Router.identity, Router.name, Router.hostname):
        r = db.query(Router).filter(col == hostname).first()
        if r:
            return r
    return None


def _create_alert(db, router_id, alert_type, severity, title, message):
    existing = db.query(Alert).filter(
        Alert.router_id == router_id,
        Alert.alert_type == alert_type,
        Alert.is_resolved == False,
    ).first()
    if existing:
        return False
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
        return False
    return True


def _parse_syslog(msg_bytes: bytes):
    text = msg_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return None

    pri = 13
    body = text
    pri_m = re.match(r"<(\d+)>\s*", text)
    if pri_m:
        pri = int(pri_m.group(1))
        body = text[pri_m.end():].strip()

    rest = body
    ts_patterns = [
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|Z)?)\s+",
        r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+",
    ]
    timestamp = None
    for pat in ts_patterns:
        m = re.match(pat, rest, re.IGNORECASE)
        if m:
            timestamp = m.group(1)
            rest = rest[m.end():]
            break

    host_m = re.match(r"(\S+)\s+", rest)
    if not host_m:
        return None
    hostname = host_m.group(1)
    rest = rest[host_m.end():].strip()

    topics = ""
    message = rest
    sep_m = re.match(r"([\w,\-]+):\s*(.*)", rest)
    if sep_m:
        topics = sep_m.group(1)
        message = sep_m.group(2)

    severity = _classify_severity(topics) if topics else "info"
    return {
        "hostname": hostname,
        "topics": topics,
        "message": message or "",
        "severity": severity,
        "timestamp": timestamp,
    }


def _handle_message(msg_bytes: bytes):
    parsed = _parse_syslog(msg_bytes)
    if not parsed:
        return

    db = SessionLocal()
    try:
        router = _find_router(db, parsed["hostname"])
        if not router:
            logger.debug(f"Syslog hostname desconocido: {parsed['hostname']}")
            return

        content_hash = _make_hash(
            router.id, "", parsed.get("timestamp") or "",
            parsed["topics"], parsed["message"]
        )
        existing = db.query(EventLog).filter(EventLog.content_hash == content_hash).first()
        if existing:
            existing.last_seen = datetime.now(timezone.utc)
            db.commit()
            return

        from app.core.event_filter import load_exclusion_filters, is_event_excluded
        excl_filters = load_exclusion_filters(db)
        if is_event_excluded(parsed["message"], parsed["topics"], excl_filters):
            return

        event = EventLog(
            router_id=router.id,
            router_name=router.name,
            ros_time=parsed.get("timestamp") or "",
            topics=parsed["topics"],
            message=parsed["message"],
            severity=parsed["severity"],
            content_hash=content_hash,
        )
        db.add(event)
        try:
            db.flush()
        except Exception:
            db.rollback()
            return

        sev = parsed["severity"]
        if sev in ("warning", "critical"):
            from app.api.v1.settings import get_setting, notify
            if get_setting(db, "log_alerts_enabled", "true") != "true":
                db.commit()
                return

            alert_type = "log_warning" if sev == "warning" else "log_critical"
            created = _create_alert(
                db, router.id, alert_type, sev,
                f"{router.name}: {sev}",
                parsed["message"][:200],
            )
            repeat_key = "notify_repeat_critical" if sev == "critical" else "notify_repeat_warning"
            if created or get_setting(db, repeat_key, "true") == "true":
                icon = "🔴" if sev == "critical" else "🟡"
                tg_msg = f"{icon} <b>{router.name}: {sev} (syslog)</b>\n{parsed['message'][:200]}"
                notify(
                    f"{router.name}: {sev}",
                    parsed["message"][:200],
                    tg_msg,
                    sev,
                    message=parsed["message"][:500],
                    topics=parsed["topics"],
                )
        db.commit()
    except Exception as e:
        logger.error(f"Error procesando syslog: {e}")
        db.rollback()
    finally:
        db.close()


def _syslog_worker():
    """Procesa mensajes de la cola en segundo plano."""
    while not _stop_event.is_set():
        try:
            msg_bytes = _msg_queue.get(timeout=1.0)
        except Exception:
            continue
        try:
            _handle_message(msg_bytes)
        except Exception as e:
            logger.error(f"Error en worker syslog: {e}")


def _run_syslog_server():
    from app.api.v1.settings import get_interval, get_setting as _get_setting

    def _is_enabled():
        db = SessionLocal()
        try:
            return _get_setting(db, "syslog_enabled", "false") == "true"
        except Exception:
            return False
        finally:
            db.close()

    port = get_interval("syslog_port", 5140)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # 256 KB buffer
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        logger.error(f"No se pudo bindear puerto syslog {port}: {e}")
        sock.close()
        return

    logger.info(f" Syslog receiver escuchando en UDP {port} (buffer 256 KB)")
    sock.settimeout(1.0)

    # Iniciar worker thread
    global _worker_thread
    _worker_thread = threading.Thread(target=_syslog_worker, daemon=True, name="syslog-worker")
    _worker_thread.start()

    _last_setting_check = time.time()
    while not _stop_event.is_set():
        try:
            data, addr = sock.recvfrom(4096)
            if data:
                try:
                    _msg_queue.put_nowait(data)
                except QueueFull:
                    logger.warning("Cola syslog llena, descartando mensaje")
        except socket.timeout:
            now = time.time()
            if now - _last_setting_check > 60:
                _last_setting_check = now
                if not _is_enabled():
                    logger.info("Syslog receiver disabled via runtime setting change")
                    break
            continue
        except Exception as e:
            logger.error(f"Error en syslog socket: {e}")
    sock.close()
    logger.info("Syslog receiver detenido")


def start_syslog_receiver():
    from app.api.v1.settings import get_setting as _get_setting
    db = SessionLocal()
    try:
        enabled = _get_setting(db, "syslog_enabled", "false") == "true"
    except Exception:
        enabled = False
    finally:
        db.close()
    if not enabled:
        logger.info("Syslog receiver disabled via setting")
        return
    global _syslog_thread
    if _syslog_thread and _syslog_thread.is_alive():
        return
    _stop_event.clear()
    _syslog_thread = threading.Thread(
        target=_run_syslog_server, daemon=True, name="syslog-receiver"
    )
    _syslog_thread.start()
    logger.info("Syslog receiver thread started")


def stop_syslog_receiver():
    _stop_event.set()
