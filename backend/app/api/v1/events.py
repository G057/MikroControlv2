import asyncio, json, logging
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import get_db
from app.core.security import get_current_user, get_user_permissions
from app.models.user import User
from app.models.event_log import EventLog
from app.models.alert import Alert
from app.services.log_fetcher import fetch_all_logs
from app.core import event_filter
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from pydantic import BaseModel
from typing import Optional

from datetime import datetime, timedelta
logger = logging.getLogger(__name__)
router = APIRouter()


class EventLogResponse(BaseModel):
    id: int
    router_id: int
    router_name: str
    ros_time: str
    topics: str
    message: str
    severity: str
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source: str = "router"

    class Config:
        from_attributes = True


class AlertEventResponse(BaseModel):
    id: int
    router_id: Optional[int] = None
    alert_type: str
    severity: str
    title: str
    message: Optional[str] = None
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_comment: Optional[str] = None
    created_at: Optional[datetime] = None
    source: str = "health"

    class Config:
        from_attributes = True


@router.get("/", response_model=list)
def list_events(
    severity: Optional[str] = None,
    topic: Optional[str] = None,
    router_id: Optional[int] = None,
    search: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    source: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _list_events(severity, topic, router_id, search, is_resolved, source, limit, db, current_user)
    except Exception as e:
        logger.error(f"list_events error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al cargar eventos: {type(e).__name__}: {e}")


def _list_events(severity, topic, router_id, search, is_resolved, source, limit, db, current_user):
    events = []

    allowed_cats = event_filter.load_role_event_categories(current_user.role, db)
    is_admin = (current_user.role == "admin")
    see_all = is_admin or ("*" in allowed_cats)
    all_rules = event_filter.load_exclusion_filters(db)
    excl_filters = event_filter.filter_rules_for_role(all_rules, current_user.role)
    visible_ids = get_visible_router_ids(current_user, db)
    router_blocked = visible_ids is not None and router_id is not None and int(router_id) not in visible_ids

    if source != "router":
        health_events = []
        has_sensitive = "routers:view_sensitive" in get_user_permissions(current_user)
        aq_all = db.query(Alert)
        if severity:
            aq_all = aq_all.filter(Alert.severity == severity)
        if router_id:
            aq_all = aq_all.filter(Alert.router_id == router_id)
        if is_resolved is not None:
            aq_all = aq_all.filter(Alert.is_resolved == is_resolved)
        for a in aq_all.order_by(desc(Alert.id)).all():
            if router_blocked:
                continue
            if visible_ids is not None and a.router_id is not None and a.router_id not in visible_ids:
                continue
            alert_msg = a.title + (f" — {a.message}" if a.message else "")
            if not has_sensitive:
                alert_msg = a.title
            if event_filter.is_event_excluded(alert_msg, a.alert_type, excl_filters):
                continue
            if allowed_cats and not see_all and event_filter.classify_alert_category(a.alert_type) not in allowed_cats:
                continue
            router_name = ""
            if a.router_id:
                from app.models.router import Router as RouterModel
                r = db.query(RouterModel).filter(RouterModel.id == a.router_id).first()
                if r:
                    router_name = r.name
            sort_time = (a.created_at - timedelta(hours=3)).isoformat() if a.created_at else None
            msg = a.title + (f" — {a.message}" if a.message else "") if has_sensitive else a.title
            health_events.append({
                "id": f"a_{a.id}", "router_id": a.router_id, "router_name": router_name,
                "time": a.created_at.strftime("%H:%M:%S") if a.created_at else "",
                "topics": a.alert_type, "message": msg,
                "severity": a.severity,
                "created_at": utc_iso(a.created_at),
                "sort_time": sort_time,
                "source": "health", "is_resolved": a.is_resolved,
                "resolved_at": utc_iso(a.resolved_at),
                "resolved_by": a.resolved_by, "resolution_comment": getattr(a, 'resolution_comment', None),
            })

        # Calcular cuántos EventLogs entran (reservar espacio para health events)
        router_limit = limit - len(health_events)

    if source != "health":
        router_can_see = see_all or bool(allowed_cats)
        if router_can_see and not router_blocked:
            q = db.query(EventLog)
            if severity:
                q = q.filter(EventLog.severity == severity)
            if topic:
                q = q.filter(EventLog.topics.contains(topic))
            if router_id:
                q = q.filter(EventLog.router_id == router_id)
            if search:
                q = q.filter(EventLog.message.contains(search))
            if visible_ids is not None:
                q = q.filter(EventLog.router_id.in_(visible_ids))

            actual_limit = router_limit if source != "router" else limit
            base_q = q.order_by(desc(EventLog.id))
            offset = 0
            batch = 500
            max_fetched = 20000
            fetched = 0
            while len(events) < actual_limit and fetched < max_fetched:
                rows = base_q.limit(batch).offset(offset).all()
                if not rows:
                    break
                for el in rows:
                    if event_filter.is_event_excluded(el.message, el.topics, excl_filters):
                        continue
                    if allowed_cats and not see_all and event_filter.classify_category(el.topics) not in allowed_cats:
                        continue
                    events.append({
                        "id": f"el_{el.id}",
                        "router_id": el.router_id,
                        "router_name": el.router_name,
                        "time": el.ros_time,
                        "topics": el.topics,
                        "message": el.message,
                        "severity": el.severity,
                        "created_at": utc_iso(el.first_seen),
                        "sort_time": (el.first_seen - timedelta(hours=3)).strftime("%Y-%m-%dT") + el.ros_time if el.first_seen and el.ros_time else (el.first_seen.isoformat() if el.first_seen else None),
                        "source": "router",
                    })
                    if len(events) >= actual_limit:
                        break
                offset += batch
                fetched += len(rows)

    if source != "router":
        # Fusionar health events + EventLogs, orden cronológico
        events = health_events + events

    # Orden cronológico descendente (por sort_time que refleja la hora real del evento)
    events.sort(key=lambda e: e.get("sort_time") or "", reverse=True)
    # Si hay críticas no resueltas, asegurar que estén al inicio
    unresolved_crit = [e for e in events if e.get("source") == "health" and e.get("severity") == "critical" and not e.get("is_resolved", True)]
    rest = [e for e in events if not (e.get("source") == "health" and e.get("severity") == "critical" and not e.get("is_resolved", True))]
    events = unresolved_crit + rest
    events = events[:limit]

    return events


@router.get("/count")
def events_count(
    severity: Optional[str] = None,
    router_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_cats = event_filter.load_role_event_categories(current_user.role, db)
    is_admin = (current_user.role == "admin")
    see_all = is_admin or ("*" in allowed_cats)
    all_rules = event_filter.load_exclusion_filters(db)
    excl_filters = event_filter.filter_rules_for_role(all_rules, current_user.role)
    visible_ids = get_visible_router_ids(current_user, db)
    router_blocked = visible_ids is not None and router_id is not None and int(router_id) not in visible_ids

    q = db.query(EventLog)
    if severity:
        q = q.filter(EventLog.severity == severity)
    if router_id:
        q = q.filter(EventLog.router_id == router_id)
    if visible_ids is not None:
        q = q.filter(EventLog.router_id.in_(visible_ids))
    total = 0
    if (see_all or allowed_cats) and not router_blocked:
        for row in q.all():
            if event_filter.is_event_excluded(row.message, row.topics, excl_filters):
                continue
            if allowed_cats and not see_all and event_filter.classify_category(row.topics) not in allowed_cats:
                continue
            total += 1

    aq = db.query(Alert).filter(Alert.is_resolved == False)
    if severity:
        aq = aq.filter(Alert.severity == severity)
    if router_id:
        aq = aq.filter(Alert.router_id == router_id)
    health_total = 0
    for a in aq.all():
        if router_blocked:
            continue
        if visible_ids is not None and a.router_id is not None and a.router_id not in visible_ids:
            continue
        alert_msg = a.title + (f" — {a.message}" if a.message else "")
        if event_filter.is_event_excluded(alert_msg, a.alert_type, excl_filters):
            continue
        if allowed_cats and not see_all and event_filter.classify_alert_category(a.alert_type) not in allowed_cats:
            continue
        health_total += 1

    return {"router_events": total, "active_alerts": health_total}


@router.get("/counts-by-severity")
def counts_by_severity(
    source: Optional[str] = None,
    router_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_cats = event_filter.load_role_event_categories(current_user.role, db)
    is_admin = (current_user.role == "admin")
    see_all = is_admin or ("*" in allowed_cats)
    all_rules = event_filter.load_exclusion_filters(db)
    excl_filters = event_filter.filter_rules_for_role(all_rules, current_user.role)
    visible_ids = get_visible_router_ids(current_user, db)
    router_blocked = visible_ids is not None and router_id is not None and int(router_id) not in visible_ids

    counts = {"critical": 0, "warning": 0, "info": 0}

    if source != "health":
        q = db.query(EventLog)
        if router_id:
            q = q.filter(EventLog.router_id == router_id)
        if search:
            q = q.filter(EventLog.message.contains(search))
        if visible_ids is not None:
            q = q.filter(EventLog.router_id.in_(visible_ids))
        if see_all or allowed_cats:
            if not router_blocked:
                for row in q.all():
                    if event_filter.is_event_excluded(row.message, row.topics, excl_filters):
                        continue
                    if allowed_cats and not see_all and event_filter.classify_category(row.topics) not in allowed_cats:
                        continue
                    if row.severity in counts:
                        counts[row.severity] += 1

    if source != "router":
        aq = db.query(Alert)
        if router_id:
            aq = aq.filter(Alert.router_id == router_id)
        for a in aq.all():
            if router_blocked:
                continue
            if visible_ids is not None and a.router_id is not None and a.router_id not in visible_ids:
                continue
            alert_msg = a.title + (f" — {a.message}" if a.message else "")
            if event_filter.is_event_excluded(alert_msg, a.alert_type, excl_filters):
                continue
            if allowed_cats and not see_all and event_filter.classify_alert_category(a.alert_type) not in allowed_cats:
                continue
            if a.severity in counts:
                counts[a.severity] += 1

    return counts


@router.post("/refresh")
def refresh_logs():
    fetch_all_logs()
    return {"status": "ok"}


@router.get("/categories")
def event_categories():
    return event_filter.EVENT_CATEGORIES


@router.get("/stream")
async def event_stream(token: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """SSE endpoint: envía notificaciones en tiempo real cuando hay
    nuevas alertas críticas o cambios de estado de routers."""
    async def generate():
        last_alert_id = 0
        last_router_status = {}
        has_sensitive = "routers:view_sensitive" in get_user_permissions(current_user)
        while True:
            try:
                from app.core.database import SessionLocal
                from sqlalchemy import desc
                db = SessionLocal()
                latest = db.query(Alert).filter(
                    Alert.is_resolved == False,
                    Alert.severity == "critical",
                    Alert.id > last_alert_id,
                ).order_by(Alert.id).all()
                for a in latest:
                    data = {
                        "type": "new_alert",
                        "id": f"a_{a.id}",
                        "alert_type": a.alert_type,
                        "severity": a.severity,
                        "title": a.title,
                        "message": a.message if has_sensitive else "",
                        "router_id": a.router_id,
                        "time": a.created_at.isoformat() if a.created_at else "",
                    }
                    yield f"event: alert\ndata: {json.dumps(data)}\n\n"
                    if a.id > last_alert_id:
                        last_alert_id = a.id
                db.close()
            except Exception:
                pass
            # Heartbeat cada 15s para mantener conexión
            yield f": heartbeat\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")
