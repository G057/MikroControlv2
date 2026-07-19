"""RouterOS log recovery service. It is intentionally not a permanent poller."""
import logging
import hashlib
import re
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.router import Router
from app.services.event_pipeline import NormalizedEvent, ingest_event

logger = logging.getLogger(__name__)
_DISK_LOG_NAME = re.compile(r"(?:^|/)log(?:\.\d+)?\.txt$", re.IGNORECASE)
_MAX_DISK_LOG_BYTES = 1_000_000


def _parse_disk_log_line(line: str):
    parts = line.strip().split(maxsplit=3)
    if len(parts) >= 4 and ("/" in parts[0] or "-" in parts[0]) and ":" in parts[1]:
        return f"{parts[0]} {parts[1]}", parts[2], parts[3]
    if len(parts) >= 3 and ":" in parts[0]:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) >= 2:
        return "", parts[0], " ".join(parts[1:])
    return None


def _read_disk_logs(conn):
    """Returns RouterOS persistent log lines when disk logging is configured."""
    entries = []
    total = 0
    for item in conn.command("/file/print"):
        name = item.get("name", "")
        if not _DISK_LOG_NAME.search(name) or not item.get(".id"):
            continue
        try:
            result = conn.command(f"/file/get =.id={item['.id']} =value-name=contents")
            content = (result[0].get("ret") or result[0].get("contents") or "") if result else ""
        except Exception as exc:
            logger.debug("No se pudo leer log persistente %s: %s", name, exc)
            continue
        remaining = _MAX_DISK_LOG_BYTES - total
        if remaining <= 0:
            break
        content = content[-remaining:]
        total += len(content.encode("utf-8", "replace"))
        for line in content.splitlines():
            parsed = _parse_disk_log_line(line)
            if not parsed:
                continue
            ros_time, topics, message = parsed
            line_hash = hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()[:16]
            entries.append({"time": ros_time, "topics": topics, "message": message,
                            ".id": f"disk:{name}:{line_hash}"})
    return entries


def recover_logs(router_id: int, reason: str = "manual", since_marker: str | None = None):
    db = SessionLocal()
    try:
        router = db.get(Router, router_id)
        if not router:
            raise ValueError("Router no encontrado")
        from app.services.routeros_service import shared_connection
        with shared_connection(router) as conn:
            logs = conn.command("/log/print")
            # Disk logs survive a reboot while the in-memory /log buffer does
            # not. Their entries are deduplicated by the event pipeline.
            disk_logs = _read_disk_logs(conn)
            logs.extend(disk_logs)
        result = {"router_id": router_id, "reason": reason, "consulted": len(logs), "new": 0,
                  "duplicates": 0, "errors": [], "started_at": datetime.now(timezone.utc).isoformat()}
        for entry in logs:
            message = entry.get("message", "")
            if not message:
                continue
            try:
                _, created, _, _ = ingest_event(db, NormalizedEvent(router.id, router.name, "log_recovery",
                    entry.get("topics", ""), message, ros_time=entry.get("time", ""), raw_message=message,
                    metadata={"ros_id": entry.get(".id", ""), "recovery_reason": reason}))
                result["new" if created else "duplicates"] += 1
            except Exception as exc:
                result["errors"].append(str(exc)[:200])
        db.commit()
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_router_logs(db, router: Router) -> int:
    """Compatibility wrapper for callers that still invoke a manual refresh."""
    result = recover_logs(router.id, "manual")
    return result["new"]


def fetch_all_logs():
    db = SessionLocal()
    try:
        ids = [router_id for (router_id,) in db.query(Router.id).filter(Router.is_online == True).all()]
    finally:
        db.close()
    results = []
    for router_id in ids:
        try:
            results.append(recover_logs(router_id, "manual_bulk"))
        except Exception as exc:
            logger.warning("Log recovery failed for router %s: %s", router_id, exc)
    return results


def start_log_fetcher():
    """Deprecated compatibility hook: recovery is trigger-driven, not polling."""
    logger.info("Log recovery service ready; continuous /log/print polling is disabled")


def stop_log_fetcher():
    return None
