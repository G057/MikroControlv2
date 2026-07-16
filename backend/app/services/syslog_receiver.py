import logging
import re
import socket
import threading
import time
from datetime import datetime, timezone
from queue import Empty, Full, Queue

from app.core.database import SessionLocal
from app.models.monitoring import SyslogMetric, UnmatchedSyslogMessage
from app.models.router import Router
from app.services.event_pipeline import NormalizedEvent, ingest_event

logger = logging.getLogger(__name__)
_syslog_thread = None
_worker_threads = []
_stop_event = threading.Event()
_msg_queue = None

_PRI_SEVERITY = {
    0: "critical", 1: "critical", 2: "critical", 3: "critical",
    4: "warning", 5: "info", 6: "info", 7: "info",
}


def _setting_int(key, default):
    from app.api.v1.settings import get_setting
    db = SessionLocal()
    try:
        return max(1, int(get_setting(db, key, str(default))))
    except (TypeError, ValueError):
        return default
    finally:
        db.close()


def _metric(db, key, amount=1):
    row = db.get(SyslogMetric, key)
    if not row:
        row = SyslogMetric(key=key, value=0)
        db.add(row)
    row.value += amount


def _parse_syslog(msg_bytes: bytes):
    if len(msg_bytes) > 8192:
        raise ValueError("message_too_large")
    text = msg_bytes.decode("utf-8", errors="replace").replace("\x00", " ").strip()
    if not text:
        raise ValueError("empty_message")
    priority = 13
    pri_match = re.match(r"^<(\d{1,3})>\s*", text)
    if pri_match:
        priority = int(pri_match.group(1))
    body = re.sub(r"^<\d{1,3}>\s*", "", text)
    timestamp = ""
    match = re.match(r"((?:\d{4}-\d\d-\d\d[T ])?\d{1,2}:\d\d:\d\d|\w{3}\s+\d{1,2}\s+\d\d:\d\d:\d\d)\s+", body)
    if match:
        timestamp, body = match.group(1), body[match.end():]
    host = re.match(r"(\S+)\s+(.+)$", body)
    if not host:
        raise ValueError("missing_hostname")
    hostname, rest = host.group(1)[:200], host.group(2)
    topic = re.match(r"([\w,-]{1,200}):\s*(.*)$", rest)
    topics = topic.group(1) if topic else ""
    # RouterOS BSD Syslog can repeat the identity before its message.
    if topics.lower() == hostname.lower():
        topics = ""
    return {"hostname": hostname, "topics": topics,
            "message": (topic.group(2) if topic else rest)[:8000], "timestamp": timestamp,
            "severity": _PRI_SEVERITY.get(priority % 8, "info"),
            "raw_message": text[:8000]}


def _find_router(db, source_ip, hostname, raw_message):
    # An explicit source address is authoritative. Never choose a non-unique fallback.
    candidates = db.query(Router).filter(Router.ip_address == source_ip).all()
    if len(candidates) == 1:
        return candidates[0], []
    candidates = []
    for col in (Router.identity, Router.hostname, Router.name):
        matches = db.query(Router).filter(col == hostname).all()
        if len(matches) == 1:
            return matches[0], []
        candidates.extend(matches)

    # RFC3164 hostnames should not contain spaces, but RouterOS identities often
    # do. Match only a complete configured identifier at the beginning of the
    # post-timestamp payload; never infer from message text elsewhere.
    payload = re.sub(r"^<\d{1,3}>\s*(?:\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+)?", "", raw_message or "", flags=re.IGNORECASE)
    header_matches = []
    for router in db.query(Router).all():
        for value in (router.identity, router.name, router.hostname):
            if value and payload.lower().startswith(f"{value.lower()} "):
                header_matches.append(router)
                break
    if len(header_matches) == 1:
        return header_matches[0], []
    candidates.extend(header_matches)
    return None, sorted({router.id for router in candidates})


def _store_unmatched(db, source_ip, parsed, reason, candidates):
    db.add(UnmatchedSyslogMessage(source_ip=source_ip, parsed_hostname=parsed.get("hostname"),
                                  raw_message=parsed.get("raw_message", ""), reason=reason,
                                  candidate_router_ids=candidates))
    _metric(db, "syslog_unmatched_total")


def _handle_message(msg_bytes, source_ip):
    db = SessionLocal()
    try:
        _metric(db, "syslog_received_total")
        try:
            parsed = _parse_syslog(msg_bytes)
        except ValueError as exc:
            _metric(db, "syslog_parse_errors_total")
            _store_unmatched(db, source_ip, {"raw_message": msg_bytes.decode("utf-8", "replace")[:8000]}, str(exc), [])
            db.commit()
            return
        router, candidates = _find_router(db, source_ip, parsed["hostname"], parsed["raw_message"])
        if not router:
            _store_unmatched(db, source_ip, parsed, "ambiguous_router" if candidates else "router_not_found", candidates)
            db.commit()
            return
        event, created, _, _ = ingest_event(db, NormalizedEvent(router.id, router.name, "syslog", parsed["topics"],
            parsed["message"], severity=parsed["severity"], ros_time=parsed["timestamp"], raw_message=parsed["raw_message"],
            metadata={"source_ip": source_ip, "parsed_hostname": parsed["hostname"]}))
        _metric(db, "syslog_parsed_total")
        if not created:
            _metric(db, "syslog_duplicate_total")
        elif event.event_type == "unclassified":
            _metric(db, "syslog_unclassified_total")
        db.commit()
    except Exception as exc:
        logger.exception("Error procesando syslog: %s", exc)
        db.rollback()
        try:
            _metric(db, "syslog_db_errors_total")
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _worker():
    while not _stop_event.is_set():
        try:
            data, source_ip = _msg_queue.get(timeout=1)
        except Empty:
            continue
        try:
            _handle_message(data, source_ip)
        finally:
            _msg_queue.task_done()


def _record_drop(data, source_ip):
    db = SessionLocal()
    try:
        parsed = {"raw_message": data.decode("utf-8", "replace")[:8000]}
        try:
            parsed.update(_parse_syslog(data))
        except ValueError:
            pass
        _store_unmatched(db, source_ip, parsed, "queue_full", [])
        _metric(db, "syslog_queue_dropped_total")
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _run_server():
    from app.api.v1.settings import get_interval
    port = get_interval("syslog_port", 5140)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as exc:
        logger.error("No se pudo bindear syslog UDP %s: %s", port, exc)
        return
    sock.settimeout(1)
    logger.info("Syslog receiver listening on UDP %s", port)
    while not _stop_event.is_set():
        try:
            data, address = sock.recvfrom(8192)
            try:
                _msg_queue.put_nowait((data, address[0]))
            except Full:
                logger.warning("Syslog queue full; persisted dropped message from %s", address[0])
                _record_drop(data, address[0])
        except socket.timeout:
            continue
        except OSError as exc:
            logger.error("Syslog socket error: %s", exc)
    sock.close()


def start_syslog_receiver():
    from app.api.v1.settings import get_setting
    db = SessionLocal()
    try:
        if get_setting(db, "syslog_enabled", "false") != "true":
            return
    finally:
        db.close()
    global _syslog_thread, _msg_queue, _worker_threads
    if _syslog_thread and _syslog_thread.is_alive():
        return
    _stop_event.clear()
    _msg_queue = Queue(maxsize=_setting_int("syslog_queue_max_size", 500))
    _worker_threads = [threading.Thread(target=_worker, daemon=True, name=f"syslog-worker-{i}")
                       for i in range(_setting_int("syslog_worker_count", 1))]
    for worker in _worker_threads:
        worker.start()
    _syslog_thread = threading.Thread(target=_run_server, daemon=True, name="syslog-receiver")
    _syslog_thread.start()


def stop_syslog_receiver():
    _stop_event.set()
