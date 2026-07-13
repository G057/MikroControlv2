from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.core.security import require_permission
from app.models.user import User
from app.models.audit import AuditLog
from app.models.router_history import RouterHistory

router = APIRouter()


@router.get("/")
def list_audit_logs(
    page: int = 1,
    limit: int = 50,
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username == username)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if search:
        sf = f"%{search}%"
        query = query.filter(
            (AuditLog.resource_name.ilike(sf)) |
            (AuditLog.username.ilike(sf)) |
            (AuditLog.action.ilike(sf))
        )
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            query = query.filter(AuditLog.timestamp >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query = query.filter(AuditLog.timestamp <= dt)
        except ValueError:
            pass

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": log.resource_name,
                "details": log.details,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None,
            }
            for log in logs
        ],
    }


@router.get("/filters")
def get_audit_filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    actions = [r[0] for r in db.query(AuditLog.action).distinct().all()]
    resource_types = [r[0] for r in db.query(AuditLog.resource_type).distinct().all()]
    usernames = [r[0] for r in db.query(AuditLog.username).distinct().all()]
    return {
        "actions": sorted(actions),
        "resource_types": sorted(resource_types),
        "usernames": sorted(usernames),
    }


@router.get("/stats")
def get_audit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    total = db.query(func.count(AuditLog.id)).scalar() or 0

    by_action = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .all()
    )

    by_resource = (
        db.query(AuditLog.resource_type, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.resource_type)
        .order_by(func.count(AuditLog.id).desc())
        .all()
    )

    by_user = (
        db.query(AuditLog.username, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.username)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total": total,
        "by_action": [{"action": a, "count": c} for a, c in by_action],
        "by_resource": [{"resource_type": r, "count": c} for r, c in by_resource],
        "by_user": [{"username": u, "count": c} for u, c in by_user],
    }


@router.get("/router-history")
def list_router_history(
    page: int = 1,
    limit: int = 50,
    router_id: Optional[int] = None,
    by_user: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    query = db.query(RouterHistory)
    if router_id:
        query = query.filter(RouterHistory.router_id == router_id)
    if by_user:
        query = query.filter(RouterHistory.by_user == by_user)
    if search:
        sf = f"%{search}%"
        query = query.filter(
            (RouterHistory.action.ilike(sf)) |
            (RouterHistory.redo.ilike(sf)) |
            (RouterHistory.router_name.ilike(sf))
        )
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            query = query.filter(RouterHistory.first_seen >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query = query.filter(RouterHistory.first_seen <= dt)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(RouterHistory.id.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "entries": [
            {
                "id": e.id,
                "router_id": e.router_id,
                "router_name": e.router_name,
                "ros_id": e.ros_id,
                "action": e.action,
                "redo": e.redo,
                "undo": e.undo,
                "by_user": e.by_user,
                "policy": e.policy,
                "ros_time": e.ros_time,
                "trace": e.trace,
                "undoable": e.undoable,
                "first_seen": e.first_seen.isoformat() + "Z" if e.first_seen else None,
            }
            for e in entries
        ],
    }


@router.get("/router-history/filters")
def router_history_filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    routers = [(r[0], r[1]) for r in db.query(RouterHistory.router_id, RouterHistory.router_name).distinct().all()]
    users = [r[0] for r in db.query(RouterHistory.by_user).distinct().all()]
    return {
        "routers": [{"id": rid, "name": name} for rid, name in routers],
        "users": sorted([u for u in users if u]),
    }


@router.get("/router-history/stats")
def router_history_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    total = db.query(func.count(RouterHistory.id)).scalar() or 0
    by_router = (
        db.query(RouterHistory.router_name, func.count(RouterHistory.id).label("count"))
        .group_by(RouterHistory.router_name)
        .order_by(func.count(RouterHistory.id).desc())
        .all()
    )
    by_user = (
        db.query(RouterHistory.by_user, func.count(RouterHistory.id).label("count"))
        .group_by(RouterHistory.by_user)
        .order_by(func.count(RouterHistory.id).desc())
        .limit(10)
        .all()
    )
    return {
        "total": total,
        "by_router": [{"router_name": r, "count": c} for r, c in by_router],
        "by_user": [{"by_user": u, "count": c} for u, c in by_user],
    }
