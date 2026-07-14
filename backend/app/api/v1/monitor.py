from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from app.models.user import User
from app.models.router import Router
from app.models.alert import Alert

router = APIRouter()


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

    alert_q = db.query(
        Alert.router_id,
        func.count(Alert.id).label("total"),
        func.sum(case((Alert.severity == "critical", 1), else_=0)).label("critical"),
        func.sum(case((Alert.severity == "warning", 1), else_=0)).label("warning"),
    ).filter(
        Alert.is_resolved == False,
        Alert.router_id.isnot(None)
    )
    if visible_ids is not None:
        alert_q = alert_q.filter(Alert.router_id.in_(visible_ids))
    alert_q = alert_q.group_by(Alert.router_id)

    alert_data = {}  # router_id -> {total, critical, warning}
    for r_id, total, critical, warning in alert_q.all():
        alert_data[r_id] = {
            "total": total or 0,
            "critical": critical or 0,
            "warning": warning or 0,
        }

    result = []
    for r in routers:
        ad = alert_data.get(r.id, {"total": 0, "critical": 0, "warning": 0})
        result.append({
            "id": r.id,
            "name": r.name,
            "client_name": r.client_name,
            "is_online": r.is_online,
            "alert_count": ad["total"],
            "critical_count": ad["critical"],
            "warning_count": ad["warning"],
            "last_seen": utc_iso(r.last_seen),
            "group_id": r.group_id,
            "city": r.city,
        })

    return result
