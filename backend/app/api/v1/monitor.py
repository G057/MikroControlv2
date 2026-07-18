from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from app.core.event_filter import load_popup_filters, is_event_excluded
from app.models.user import User
from app.models.router import Router
from app.models.alert import Alert
from app.models.event_log import EventLog
from app.models.monitoring import Notification
from app.utils.audit import log_audit

router = APIRouter()


@router.get("/notifications")
def get_notifications(
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("monitor:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    now = datetime.now(timezone.utc)
    q = db.query(Notification).filter(
        Notification.id > after_id,
        Notification.status != "acknowledged",
        Notification.suppressed_at.is_(None),
        (Notification.available_after.is_(None)) | (Notification.available_after <= now),
    )
    if visible_ids is not None:
        q = q.filter((Notification.router_id.is_(None)) | (Notification.router_id.in_(visible_ids)))
    rows = q.order_by(Notification.id.asc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    withheld = db.query(Notification.id).filter(
        Notification.id > after_id,
        Notification.status != "acknowledged",
        Notification.suppressed_at.is_(None),
        Notification.available_after > now,
    )
    if visible_ids is not None:
        withheld = withheld.filter((Notification.router_id.is_(None)) | (Notification.router_id.in_(visible_ids)))
    # Keep the cursor behind delayed rows. The frontend de-duplicates repeated
    # immediate rows until the delayed notification becomes available.
    next_cursor = after_id if withheld.first() else (rows[-1].id if rows else after_id)
    return {"items": [{"id": n.id, "eventLogId": n.event_log_id, "alertId": n.alert_id,
                        "routerId": n.router_id, "notificationType": n.notification_type,
                        "severity": n.severity, "title": n.title, "message": n.message,
                        "popupRequired": n.popup_required, "soundRequired": n.sound_required,
                        "status": n.status, "occurrenceCount": n.occurrence_count,
                        "createdAt": utc_iso(n.created_at)} for n in rows],
            "nextCursor": next_cursor, "hasMore": has_more,
            "serverTimestamp": datetime.now(timezone.utc).isoformat()}


@router.put("/notifications/{notification_id}/acknowledge")
def acknowledge_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("monitor:view")),
):
    item = db.get(Notification, notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None and item.router_id is not None and item.router_id not in visible_ids:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    item.status = "acknowledged"
    item.acknowledged_at = datetime.now(timezone.utc)
    item.acknowledged_by = current_user.username
    db.commit()
    return {"status": item.status}


@router.put("/notifications/acknowledge-all")
def acknowledge_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("monitor:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    query = db.query(Notification).filter(
        Notification.status != "acknowledged",
        Notification.popup_required == True,
        Notification.suppressed_at.is_(None),
    )
    if visible_ids is not None:
        query = query.filter((Notification.router_id.is_(None)) | (Notification.router_id.in_(visible_ids)))
    count = query.update({
        "status": "acknowledged",
        "acknowledged_at": datetime.now(timezone.utc),
        "acknowledged_by": current_user.username,
    }, synchronize_session=False)
    log_audit(db, current_user.username, "acknowledge_all", "notification",
              details={"count": count}, user_id=current_user.id)
    db.commit()
    return {"acknowledged": count}


def _alert_counts(db, visible_ids):
    """Devuelve un dict {router_id: {total, critical, warning}}."""
    base = db.query(Alert.router_id, func.count(Alert.id).label("total")).filter(
        Alert.is_resolved == False, Alert.router_id.isnot(None)
    )
    if visible_ids is not None:
        base = base.filter(Alert.router_id.in_(visible_ids))
    base = base.group_by(Alert.router_id)

    crit = db.query(Alert.router_id, func.count(Alert.id).label("critical")).filter(
        Alert.is_resolved == False, Alert.router_id.isnot(None), Alert.severity == "critical"
    )
    if visible_ids is not None:
        crit = crit.filter(Alert.router_id.in_(visible_ids))
    crit = crit.group_by(Alert.router_id)

    warn = db.query(Alert.router_id, func.count(Alert.id).label("warning")).filter(
        Alert.is_resolved == False, Alert.router_id.isnot(None), Alert.severity == "warning"
    )
    if visible_ids is not None:
        warn = warn.filter(Alert.router_id.in_(visible_ids))
    warn = warn.group_by(Alert.router_id)

    data = {}
    for r_id, total in base.all():
        data.setdefault(r_id, {})["total"] = total or 0
    for r_id, c in crit.all():
        data.setdefault(r_id, {})["critical"] = c or 0
    for r_id, w in warn.all():
        data.setdefault(r_id, {})["warning"] = w or 0
    return data


def _new_event_counts(db, visible_ids, since_id):
    """Cuenta EventLog con id > since_id, por router y severidad.
    Si hay popup_exclusion_filters, itera los eventos y excluye los que coincidan."""
    data = {}
    if since_id is None:
        return data

    popup_filters = load_popup_filters(db)

    for sev in ("critical", "warning"):
        if popup_filters:
            # Slow path: cargar cada fila y aplicar filtros
            q = db.query(EventLog).filter(
                EventLog.severity == sev, EventLog.id > since_id
            )
            if visible_ids is not None:
                q = q.filter(EventLog.router_id.in_(visible_ids))
            for log in q.all():
                # router_offline (health critical) siempre muestra popup
                if log.topics.startswith("health,") and log.severity == "critical":
                    data.setdefault(log.router_id, {}).setdefault("critical", 0)
                    data[log.router_id]["critical"] += 1
                    continue
                if not is_event_excluded(log.message, log.topics, popup_filters):
                    data.setdefault(log.router_id, {}).setdefault(sev, 0)
                    data[log.router_id][sev] += 1
        else:
            # Fast path: COUNT
            q = db.query(EventLog.router_id, func.count(EventLog.id)).filter(
                EventLog.severity == sev, EventLog.id > since_id
            )
            if visible_ids is not None:
                q = q.filter(EventLog.router_id.in_(visible_ids))
            for r_id, cnt in q.group_by(EventLog.router_id).all():
                data.setdefault(r_id, {})[sev] = cnt
    return data


@router.get("/")
def get_monitor(
    since_event_log_id: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("monitor:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    from app.core.security import get_user_permissions
    can_view_details = "routers:details" in get_user_permissions(current_user)

    q = db.query(
        Router.id, Router.name, Router.client_name,
        Router.is_online, Router.last_seen,
        Router.group_id, Router.city
    )
    if visible_ids is not None:
        q = q.filter(Router.id.in_(visible_ids))
    routers = q.all()

    alert_data = _alert_counts(db, visible_ids)
    new_data = _new_event_counts(db, visible_ids, since_event_log_id)

    max_event_log_id = db.query(func.max(EventLog.id)).scalar() or 0

    result = []
    for r in routers:
        ad = alert_data.get(r.id, {"total": 0, "critical": 0, "warning": 0})
        nd = new_data.get(r.id, {})
        result.append({
            "id": r.id,
            "name": r.name,
            "client_name": r.client_name if can_view_details else None,
            "is_online": r.is_online,
            "alert_count": ad.get("total", 0),
            "critical_count": ad.get("critical", 0),
            "warning_count": ad.get("warning", 0),
            "new_critical_events": nd.get("critical", 0),
            "new_warning_events": nd.get("warning", 0),
            "last_seen": utc_iso(r.last_seen),
            "group_id": r.group_id,
            "city": r.city,
        })

    return {
        "routers": result,
        "max_event_log_id": max_event_log_id,
    }
