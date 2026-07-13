from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.core.database import get_db
from app.core.security import require_permission
from app.core.router_access import require_visible_router
from app.models.user import User
from app.models.interface_traffic import InterfaceTraffic

router = APIRouter()

_VIEW = require_permission("routers:view_traffic")


@router.get("/{router_id}/interfaces")
def list_traffic_interfaces(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_VIEW),
):
    """Interfaces del router que tienen muestras de tráfico registradas."""
    r = require_visible_router(router_id, current_user, db)
    rows = (
        db.query(InterfaceTraffic.interface)
        .filter(InterfaceTraffic.router_id == r.id)
        .distinct()
        .all()
    )
    return sorted(row[0] for row in rows)


@router.get("/{router_id}")
def get_traffic(
    router_id: int,
    interface: Optional[str] = None,
    hours: int = Query(1, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User = Depends(_VIEW),
):
    """Serie temporal de tráfico (rx/tx en bps) para el router/interfaz."""
    r = require_visible_router(router_id, current_user, db)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(InterfaceTraffic).filter(
        InterfaceTraffic.router_id == r.id,
        InterfaceTraffic.timestamp >= cutoff,
    )
    if interface:
        q = q.filter(InterfaceTraffic.interface == interface)
    samples = q.order_by(InterfaceTraffic.timestamp.asc()).all()

    def _iso_utc(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return [
        {
            "timestamp": _iso_utc(s.timestamp),
            "interface": s.interface,
            "rx_bps": s.rx_bps,
            "tx_bps": s.tx_bps,
        }
        for s in samples
    ]
