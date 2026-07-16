from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, cast, String
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.router_access import get_visible_router_ids
from app.core.datetime_utils import utc_iso
from app.models.user import User
from app.models.router import Router
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.inventory import InventoryItem
from app.models.event_log import EventLog
from datetime import datetime, timedelta, timezone

router = APIRouter()


@router.get("/")
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visible_ids = get_visible_router_ids(current_user, db)
    r_filter = (Router.id.in_(visible_ids)) if visible_ids is not None else None

    base = db.query(func.count(Router.id))
    online_base = db.query(func.count(Router.id)).filter(Router.is_online == True)
    if r_filter is not None:
        base = base.filter(r_filter)
        online_base = online_base.filter(r_filter)
    total_routers = base.scalar()
    online_routers = online_base.scalar()
    offline_routers = total_routers - online_routers

    avg_cpu = db.query(func.avg(Router.cpu_usage)).filter(Router.cpu_usage.isnot(None))
    avg_ram = db.query(func.avg(Router.ram_usage)).filter(Router.ram_usage.isnot(None))
    avg_temp = db.query(func.avg(Router.temperature)).filter(Router.temperature.isnot(None), Router.temperature > 0)
    avg_voltage = db.query(func.avg(Router.voltage)).filter(Router.voltage.isnot(None), Router.voltage > 0)
    avg_hdd = db.query(func.avg(Router.hdd_free)).filter(Router.hdd_free.isnot(None))
    if r_filter is not None:
        avg_cpu = avg_cpu.filter(r_filter)
        avg_ram = avg_ram.filter(r_filter)
        avg_temp = avg_temp.filter(r_filter)
        avg_voltage = avg_voltage.filter(r_filter)
        avg_hdd = avg_hdd.filter(r_filter)
    avg_cpu = avg_cpu.scalar() or 0
    avg_ram = avg_ram.scalar() or 0
    avg_temp = avg_temp.scalar() or 0
    avg_voltage = avg_voltage.scalar() or 0
    avg_hdd = avg_hdd.scalar() or 0

    if visible_ids is not None:
        alert_visible = (Alert.router_id.is_(None)) | (Alert.router_id.in_(visible_ids))
    else:
        alert_visible = None
    active_q = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False)
    crit_q = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False, Alert.severity == "critical")
    if alert_visible is not None:
        active_q = active_q.filter(alert_visible)
        crit_q = crit_q.filter(alert_visible)
    active_alerts = active_q.scalar()
    critical_alerts = crit_q.scalar()

    total_inventory = db.query(func.count(InventoryItem.id)).scalar()
    total_users = db.query(func.count(User.id)).scalar()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    ev_q = db.query(func.count(EventLog.id)).filter(EventLog.first_seen >= today_start)
    if visible_ids is not None:
        ev_q = ev_q.filter(EventLog.router_id.in_(visible_ids))
    events_today = ev_q.scalar() or 0
    commands_today = db.query(func.count(AuditLog.id)).filter(
        AuditLog.action.in_(["create", "update", "delete", "command"]),
        AuditLog.timestamp >= today_start,
    ).scalar() or 0

    wg_tunnels = db.query(func.count(Router.id)).filter(
        Router.is_online == True, Router.wg_address.isnot(None), Router.wg_address != ""
    )
    if r_filter is not None:
        wg_tunnels = wg_tunnels.filter(r_filter)
    wg_tunnels = wg_tunnels.scalar() or 0

    recent_activity = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()

    return {
        "routers": {
            "total": total_routers,
            "online": online_routers,
            "offline": offline_routers,
        },
        "metrics": {
            "avg_cpu": round(float(avg_cpu), 1),
            "avg_ram": round(float(avg_ram), 1),
            "avg_temp": round(float(avg_temp), 1),
            "avg_voltage": round(float(avg_voltage), 1),
            "avg_hdd_free": round(float(avg_hdd), 1),
        },
        "alerts": {
            "active": active_alerts,
            "critical": critical_alerts,
        },
        "inventory": {
            "total": total_inventory,
        },
        "users": {
            "total": total_users,
        },
        "today": {
            "events": events_today,
            "commands": commands_today,
        },
        "wireguard": {
            "tunnels": wg_tunnels,
        },
        "recent_activity": [
            {
                "id": log.id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_name": log.resource_name,
                "timestamp": utc_iso(log.timestamp),
            }
            for log in recent_activity
        ],
    }


@router.get("/charts")
def get_charts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visible_ids = get_visible_router_ids(current_user, db)
    r_filter = (Router.id.in_(visible_ids)) if visible_ids is not None else None
    ev_filter = (EventLog.router_id.in_(visible_ids)) if visible_ids is not None else None

    events_by_router_q = db.query(EventLog.router_name, func.count(EventLog.id).label("count"))
    if ev_filter is not None:
        events_by_router_q = events_by_router_q.filter(ev_filter)
    events_by_router = (
        events_by_router_q
        .group_by(EventLog.router_name)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )

    all_events_q = db.query(EventLog.topics, func.count(EventLog.id))
    if ev_filter is not None:
        all_events_q = all_events_q.filter(ev_filter)
    all_events = all_events_q.group_by(EventLog.topics).all()
    topic_counts: dict[str, int] = {}
    for topics, count in all_events:
        if not topics:
            continue
        for t in topics.split(","):
            t = t.strip()
            if t:
                topic_counts[t] = topic_counts.get(t, 0) + count
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    now = datetime.utcnow()
    hour_start = now - timedelta(hours=23)
    bucket = func.date_trunc("hour", EventLog.first_seen).label("bucket")
    hourly_q = db.query(bucket, EventLog.severity, func.count(EventLog.id)).filter(EventLog.first_seen >= hour_start)
    if ev_filter is not None:
        hourly_q = hourly_q.filter(ev_filter)
    hourly = {(row[0].replace(tzinfo=None), row[1]): row[2] for row in hourly_q.group_by(bucket, EventLog.severity).all()}
    severity_by_hour = []
    for i in range(24):
        point = (now - timedelta(hours=23 - i)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
        w = hourly.get((point, "warning"), 0)
        cr = hourly.get((point, "critical"), 0)
        total = sum(hourly.get((point, severity), 0) for severity in ("critical", "warning", "info", "recovery"))
        severity_by_hour.append({
            "hour": point.strftime("%H:00"),
            "critical": cr,
            "warning": w,
            "info": max(0, total - w - cr),
        })

    online_q = db.query(func.count(Router.id)).filter(Router.is_online == True)
    offline_q = db.query(func.count(Router.id)).filter(Router.is_online == False)
    if r_filter is not None:
        online_q = online_q.filter(r_filter)
        offline_q = offline_q.filter(r_filter)
    online = online_q.scalar() or 0
    offline = offline_q.scalar() or 0

    hw_rows_q = (
        db.query(func.coalesce(Router.model, "Desconocido").label("model"), func.count(Router.id).label("count"))
        .group_by("model")
        .order_by(desc("count"))
    )
    if r_filter is not None:
        hw_rows_q = hw_rows_q.filter(r_filter)
    hw_rows = hw_rows_q.all()

    return {
        "events_by_router": [{"router_name": r, "count": c} for r, c in events_by_router],
        "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
        "severity_by_hour": severity_by_hour,
        "router_status": {"online": online, "offline": offline},
        "hardware_distribution": [{"model": m, "count": c} for m, c in hw_rows],
    }
