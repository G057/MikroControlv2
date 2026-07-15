"""RouterOS log recovery service. It is intentionally not a permanent poller."""
import logging
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.router import Router
from app.services.event_pipeline import NormalizedEvent, ingest_event

logger = logging.getLogger(__name__)


def recover_logs(router_id: int, reason: str = "manual", since_marker: str | None = None):
    db = SessionLocal()
    try:
        router = db.get(Router, router_id)
        if not router:
            raise ValueError("Router no encontrado")
        from app.services.routeros_service import _get_connection
        conn = _get_connection(router)
        try:
            conn.connect()
            logs = conn.command("/log/print")
        finally:
            conn.close()
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
