from fastapi import APIRouter, Depends
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


@router.get("/")
def get_monitor(db: Session = Depends(get_db), current_user: User = Depends(require_permission("monitor:view"))):
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

    # max EventLog id por router y severidad (monotónico, nunca decrece)
    max_crit = dict(
        db.query(EventLog.router_id, func.max(EventLog.id))
        .filter(EventLog.severity == "critical")
        .group_by(EventLog.router_id).all()
    ) if visible_ids is None else dict(
        db.query(EventLog.router_id, func.max(EventLog.id))
        .filter(EventLog.severity == "critical", EventLog.router_id.in_(visible_ids))
        .group_by(EventLog.router_id).all()
    )
    max_warn = dict(
        db.query(EventLog.router_id, func.max(EventLog.id))
        .filter(EventLog.severity == "warning")
        .group_by(EventLog.router_id).all()
    ) if visible_ids is None else dict(
        db.query(EventLog.router_id, func.max(EventLog.id))
        .filter(EventLog.severity == "warning", EventLog.router_id.in_(visible_ids))
        .group_by(EventLog.router_id).all()
    )

    result = []
    for r in routers:
        ad = alert_data.get(r.id, {"total": 0, "critical": 0, "warning": 0})
        result.append({
            "id": r.id,
            "name": r.name,
            "client_name": r.client_name,
            "is_online": r.is_online,
            "alert_count": ad.get("total", 0),
            "critical_count": ad.get("critical", 0),
            "warning_count": ad.get("warning", 0),
            "max_critical_log_id": max_crit.get(r.id, 0) or 0,
            "max_warning_log_id": max_warn.get(r.id, 0) or 0,
            "last_seen": utc_iso(r.last_seen),
            "group_id": r.group_id,
            "city": r.city,
        })

    return result
