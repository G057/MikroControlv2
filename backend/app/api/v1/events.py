import asyncio, json, logging
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.core.database import get_db
from app.core.security import get_current_user, get_user_permissions, require_permission
from app.models.user import User
from app.models.event_log import EventLog
from app.models.alert import Alert
from app.services.log_fetcher import fetch_all_logs
from app.core import event_filter
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from pydantic import BaseModel
from typing import Optional

from datetime import datetime, timedelta, timezone
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
    health_events = []
    router_events = []

    allowed_cats = event_filter.load_role_event_categories(current_user.role, db)
    is_admin = (current_user.role == "admin")
    see_all = is_admin or ("*" in allowed_cats)
    all_rules = event_filter.load_exclusion_filters(db)
    excl_filters = event_filter.filter_rules_for_role(all_rules, current_user.role)
    visible_ids = get_visible_router_ids(current_user, db)
    router_blocked = visible_ids is not None and router_id is not None and int(router_id) not in visible_ids

    if source != "router":
        has_sensitive = "routers:view_sensitive" in get_user_permissions(current_user)
        from app.models.router import Router as RouterModel
        aq = db.query(Alert, RouterModel.name).outerjoin(RouterModel, RouterModel.id == Alert.router_id)
        if severity:
            aq = aq.filter(Alert.severity == severity)
        if router_id:
            aq = aq.filter(Alert.router_id == router_id)
        if is_resolved is not None:
            aq = aq.filter(Alert.is_resolved == is_resolved)
        # The events page renders a bounded recent window. Loading every alert
        # before applying role filters made initial render scale with all history.
        for a, router_name in aq.order_by(desc(Alert.id)).limit(max(limit * 2, 500)).all():
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
            health_events.append({
                "id": f"a_{a.id}", "router_id": a.router_id, "router_name": router_name or "",
                "time": a.created_at.strftime("%m/%d %H:%M:%S") if a.created_at else "",
                "topics": a.alert_type, "message": alert_msg,
                "severity": a.severity,
                "created_at": utc_iso(a.created_at),
                "sort_time": utc_iso(a.created_at) or "",
                "source": "health", "is_resolved": a.is_resolved,
                "resolved_at": utc_iso(a.resolved_at),
                "resolved_by": a.resolved_by,
                "resolution_comment": getattr(a, 'resolution_comment', None),
            })

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

            base_q = q.order_by(desc(EventLog.id))
            offset = 0
            batch = 500
            # Avoid scanning the entire event history just to fill one page.
            max_fetched = max(limit * 4, 1000)
            fetched = 0
            while len(router_events) < limit and fetched < max_fetched:
                rows = base_q.limit(batch).offset(offset).all()
                if not rows:
                    break
                for el in rows:
                    if event_filter.is_event_excluded(el.message, el.topics, excl_filters):
                        continue
                    if allowed_cats and not see_all and event_filter.classify_category(el.topics) not in allowed_cats:
                        continue
                    router_events.append({
                        "id": f"el_{el.id}",
                        "router_id": el.router_id,
                        "router_name": el.router_name,
                        "time": el.ros_time if el.ros_time else (el.first_seen.strftime("%m/%d %H:%M:%S") if el.first_seen else ""),
                        "topics": el.topics,
                        "message": el.message,
                        "severity": el.severity,
                        "created_at": utc_iso(el.first_seen),
                        "sort_time": utc_iso(el.first_seen) or "",
                        "source": "router",
                    })
                    if len(router_events) >= limit:
                        break
                offset += batch
                fetched += len(rows)

    if source == "router":
        events = router_events[:limit]
    elif source == "health":
        events = health_events[:limit]
    else:
        events = health_events + router_events

    events.sort(key=lambda e: e.get("sort_time") or "", reverse=True)
    return events[:limit]


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
    is_resolved: Optional[bool] = None,
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
    # Summary cards must stay responsive even when display-only exclusion rules
    # exist. The event list still applies those rules row by row; totals are
    # operational aggregates calculated directly by PostgreSQL.
    can_use_sql = see_all and not router_blocked

    counts = {"critical": 0, "warning": 0, "info": 0, "unresolved": 0}

    if source != "health":
        if can_use_sql:
            from sqlalchemy import func as sa_func
            q = db.query(EventLog.severity, sa_func.count(EventLog.id))
            if router_id:
                q = q.filter(EventLog.router_id == router_id)
            if search:
                q = q.filter(EventLog.message.contains(search))
            if visible_ids is not None:
                q = q.filter(EventLog.router_id.in_(visible_ids))
            for sev, cnt in q.group_by(EventLog.severity).all():
                if sev in counts:
                    counts[sev] = cnt
        else:
            q = db.query(EventLog)
            if router_id:
                q = q.filter(EventLog.router_id == router_id)
            if search:
                q = q.filter(EventLog.message.contains(search))
            if visible_ids is not None:
                q = q.filter(EventLog.router_id.in_(visible_ids))
            if see_all or allowed_cats:
                if not router_blocked:
                    batch_size = 1000
                    offset = 0
                    while True:
                        rows = q.order_by(EventLog.id).limit(batch_size).offset(offset).all()
                        if not rows:
                            break
                        for row in rows:
                            if event_filter.is_event_excluded(row.message, row.topics, excl_filters):
                                continue
                            if allowed_cats and not see_all and event_filter.classify_category(row.topics) not in allowed_cats:
                                continue
                            if row.severity in counts:
                                counts[row.severity] += 1
                        offset += batch_size

    if source != "router":
        if can_use_sql:
            from sqlalchemy import func as sa_func
            aq = db.query(Alert.severity, sa_func.count(Alert.id))
            if router_id:
                aq = aq.filter(Alert.router_id == router_id)
            if is_resolved is not None:
                aq = aq.filter(Alert.is_resolved == is_resolved)
            if visible_ids is not None:
                aq = aq.filter(Alert.router_id.in_(visible_ids))
            for sev, cnt in aq.group_by(Alert.severity).all():
                if sev in counts:
                    counts[sev] = cnt
            unresolved_q = db.query(sa_func.count(Alert.id)).filter(Alert.is_resolved == False)
            if router_id:
                unresolved_q = unresolved_q.filter(Alert.router_id == router_id)
            if visible_ids is not None:
                unresolved_q = unresolved_q.filter(Alert.router_id.in_(visible_ids))
            counts["unresolved"] = unresolved_q.scalar() or 0
        else:
            aq = db.query(Alert)
            if router_id:
                aq = aq.filter(Alert.router_id == router_id)
            if is_resolved is not None:
                aq = aq.filter(Alert.is_resolved == is_resolved)
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
                if not a.is_resolved:
                    counts["unresolved"] += 1

    return counts


@router.post("/refresh")
def refresh_logs(current_user: User = Depends(require_permission("settings:edit"))):
    fetch_all_logs()
    return {"status": "ok"}


@router.get("/categories")
def event_categories():
    return event_filter.EVENT_CATEGORIES


def _parse_date(value: Optional[str], end: bool = False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha inválida; usá ISO-8601")


@router.get("/explorer")
def explore_events(
    router_id: Optional[int] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None and router_id is not None and router_id not in visible_ids:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    q = db.query(EventLog)
    if visible_ids is not None:
        q = q.filter(EventLog.router_id.in_(visible_ids))
    if router_id:
        q = q.filter(EventLog.router_id == router_id)
    if severity:
        q = q.filter(EventLog.severity == severity)
    if search:
        q = q.filter(EventLog.message.ilike(f"%{search.strip()}%"))
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start:
        q = q.filter(EventLog.first_seen >= start)
    if end:
        q = q.filter(EventLog.first_seen <= end)
    total = q.count()
    rows = q.order_by(EventLog.first_seen.desc(), EventLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "pageSize": page_size, "items": [
        {"id": e.id, "routerId": e.router_id, "routerName": e.router_name, "severity": e.severity,
         "eventType": e.event_type, "topics": e.topics, "message": e.message,
         "source": e.source, "receivedAt": utc_iso(e.first_seen), "routerTime": e.ros_time}
        for e in rows
    ]}


@router.get("/report")
def event_report(
    router_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None and router_id not in visible_ids:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    from app.models.router import Router
    router_row = db.get(Router, router_id)
    if not router_row:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    q = db.query(EventLog).filter(EventLog.router_id == router_id)
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start:
        q = q.filter(EventLog.first_seen >= start)
    if end:
        q = q.filter(EventLog.first_seen <= end)
    summary = dict(q.with_entities(EventLog.severity, func.count(EventLog.id)).group_by(EventLog.severity).all())
    bucket = func.date_trunc("day", EventLog.first_seen).label("bucket")
    rows = q.with_entities(bucket, EventLog.severity, func.count(EventLog.id)).group_by(bucket, EventLog.severity).order_by(bucket).all()
    series = {}
    for day, sev, count in rows:
        key = utc_iso(day)[:10]
        series.setdefault(key, {"date": key, "critical": 0, "warning": 0, "info": 0})[sev if sev in ("critical", "warning", "info") else "info"] = count
    return {"router": {"id": router_row.id, "name": router_row.name, "clientName": router_row.client_name},
            "summary": {"total": sum(summary.values()), "critical": summary.get("critical", 0), "warning": summary.get("warning", 0), "info": summary.get("info", 0)},
            "series": list(series.values()), "from": date_from, "to": date_to}


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
