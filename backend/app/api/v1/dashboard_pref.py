import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.dashboard_pref import DashboardPreference

router = APIRouter()

ALL_WIDGETS = [
    {"id": "routers_online", "label": "Routers Online", "category": "routers"},
    {"id": "routers_offline", "label": "Routers Offline", "category": "routers"},
    {"id": "cpu_avg", "label": "CPU Promedio", "category": "metrics"},
    {"id": "temp_avg", "label": "Temperatura Promedio", "category": "metrics"},
    {"id": "disk_free", "label": "Disco Libre", "category": "metrics"},
    {"id": "alerts_active", "label": "Alertas Activas", "category": "alerts"},
    {"id": "events_today", "label": "Eventos Hoy", "category": "today"},
    {"id": "commands_today", "label": "Comandos Hoy", "category": "today"},
    {"id": "wireguard_tunnels", "label": "WireGuard Tunnels", "category": "network"},
    {"id": "inventory", "label": "Inventario", "category": "other"},
    {"id": "chart_severity_hour", "label": "Severidad por Hora", "category": "charts"},
    {"id": "chart_events_router", "label": "Eventos por Router", "category": "charts"},
    {"id": "chart_topics", "label": "Top Topics", "category": "charts"},
    {"id": "chart_router_status", "label": "Estado de Routers", "category": "charts"},
    {"id": "chart_hardware", "label": "Distribución de Hardware", "category": "charts"},
    {"id": "recent_activity", "label": "Actividad Reciente", "category": "other"},
]


class PrefUpdate(BaseModel):
    widgets: list[str]


@router.get("/widgets")
def list_widgets():
    return ALL_WIDGETS


@router.get("/")
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = db.query(DashboardPreference).filter(DashboardPreference.user_id == current_user.id).first()
    if pref:
        try:
            widgets = json.loads(pref.widgets)
        except Exception:
            widgets = [w["id"] for w in ALL_WIDGETS]
    else:
        widgets = [w["id"] for w in ALL_WIDGETS]
    return {"widgets": widgets}


@router.put("/")
def update_preferences(
    data: PrefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = db.query(DashboardPreference).filter(DashboardPreference.user_id == current_user.id).first()
    if pref:
        pref.widgets = json.dumps(data.widgets)
    else:
        pref = DashboardPreference(user_id=current_user.id, widgets=json.dumps(data.widgets))
        db.add(pref)
    db.commit()
    return {"widgets": data.widgets}
