from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.router_access import get_visible_router_ids
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
        func.count(Alert.id).label("alert_count")
    ).filter(
        Alert.is_resolved == False,
        Alert.router_id.isnot(None)
    )
    if visible_ids is not None:
        alert_q = alert_q.filter(Alert.router_id.in_(visible_ids))
    alert_q = alert_q.group_by(Alert.router_id)
    alert_counts = {r: c for r, c in alert_q.all()}

    result = []
    for r in routers:
        alert_count = alert_counts.get(r.id, 0)
        result.append({
            "id": r.id,
            "name": r.name,
            "client_name": r.client_name,
            "is_online": r.is_online,
            "alert_count": alert_count,
            "last_seen": r.last_seen.isoformat() + "Z" if r.last_seen else None,
            "group_id": r.group_id,
            "city": r.city,
        })

    return result
