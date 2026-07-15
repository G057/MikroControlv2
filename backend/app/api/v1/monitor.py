from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from app.models.user import User
from app.models.router import Router
from app.models.alert import Alert
from app.models.event_log import EventLog

router = APIRouter()


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
    """Cuenta EventLog con id > since_id, por router y severidad."""
    data = {}
    if since_id is None:
        return data
    for sev in ("critical", "warning"):
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
            "client_name": r.client_name,
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
