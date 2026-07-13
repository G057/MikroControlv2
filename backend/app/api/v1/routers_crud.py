from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user, require_permission, require_any_permission, get_user_permissions
from app.models.user import User
from app.models.router import Router, RouterGroup, RouterTag
from app.schemas.router import RouterCreate, RouterUpdate, RouterResponse, GroupCreate, GroupResponse, TagCreate, TagResponse
from app.utils.audit import log_audit
from app.core.router_access import get_visible_router_ids, require_visible_router

router = APIRouter()

# Cualquier permiso de vista por sección habilita listar/abrir el router
from app.core.permissions import ROUTER_VIEW_PERMS
_VIEW_PERMS = list(ROUTER_VIEW_PERMS)

# Campos técnicos sensibles: se ocultan a roles sin 'routers:view_sensitive'.
_SENSITIVE_FIELDS = ["ip_address", "hostname", "identity", "mac_address", "serial_number", "model",
                      "api_username", "wg_address", "wg_endpoint", "wg_public_key"]
_MASK = "••••••"


def _mask_sensitive(resp, current_user):
    """Enmascara IP/host/identidad/MAC/serial/modelo si el usuario no tiene permiso."""
    if "routers:view_sensitive" in get_user_permissions(current_user):
        return resp
    for f in _SENSITIVE_FIELDS:
        if getattr(resp, f, None) is not None:
            setattr(resp, f, _MASK)
    return resp


@router.get("/", response_model=List[RouterResponse])
def list_routers(
    group_id: Optional[int] = None,
    search: Optional[str] = None,
    is_online: Optional[bool] = None,
    tag_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(*_VIEW_PERMS)),
):
    query = db.query(Router)
    if group_id:
        query = query.filter(Router.group_id == group_id)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Router.name.ilike(search_filter)) |
            (Router.hostname.ilike(search_filter)) |
            (Router.ip_address.ilike(search_filter)) |
            (Router.client_name.ilike(search_filter))
        )
    if is_online is not None:
        query = query.filter(Router.is_online == is_online)
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None:
        query = query.filter(Router.id.in_(visible_ids))
    routers = query.order_by(Router.name).all()
    return [_mask_sensitive(RouterResponse.model_validate(r), current_user) for r in routers]


@router.post("/", response_model=RouterResponse)
def create_router(
    data: RouterCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    router_obj = Router(
        name=data.name,
        hostname=data.hostname,
        ip_address=data.ip_address,
        mac_address=data.mac_address,
        model=data.model,
        serial_number=data.serial_number,
        access_method=data.access_method,
        access_port=data.access_port,
        use_ssl=data.use_ssl,
        api_username=data.api_username,
        group_id=data.group_id,
        tag_ids=data.tag_ids,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        city=data.city,
        client_name=data.client_name,
        client_phone=data.client_phone,
        client_email=data.client_email,
        notes=data.notes,
        wg_address=data.wg_address,
        wg_endpoint=data.wg_endpoint,
        wg_public_key=data.wg_public_key,
    )
    if data.api_password:
        from app.core.crypto import encrypt_secret
        router_obj.api_password_encrypted = encrypt_secret(data.api_password)
    db.add(router_obj)
    db.commit()
    db.refresh(router_obj)
    log_audit(db, current_user.username, "create", "router",
              router_obj.id, router_obj.name,
              {"hostname": router_obj.hostname},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return RouterResponse.model_validate(router_obj)


@router.get("/{router_id}", response_model=RouterResponse)
def get_router(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(*_VIEW_PERMS)),
):
    r = require_visible_router(router_id, current_user, db)
    return _mask_sensitive(RouterResponse.model_validate(r), current_user)


@router.put("/{router_id}", response_model=RouterResponse)
def update_router(
    router_id: int,
    data: RouterUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    r = require_visible_router(router_id, current_user, db)

    update_data = data.model_dump(exclude_unset=True)

    # Un rol sin 'routers:view_sensitive' recibe estos campos enmascarados (••••••)
    # y no debe poder modificarlos: se descartan para no corromper los valores reales.
    if "routers:view_sensitive" not in get_user_permissions(current_user):
        for f in _SENSITIVE_FIELDS:
            update_data.pop(f, None)

    if "api_password" in update_data:
        pwd = update_data.pop("api_password")
        if pwd is not None and pwd != "":
            from app.core.crypto import encrypt_secret
            r.api_password_encrypted = encrypt_secret(pwd)

    for key, value in update_data.items():
        setattr(r, key, value)

    db.commit()
    db.refresh(r)
    log_audit(db, current_user.username, "update", "router",
              r.id, r.name, {"fields": list(data.model_dump(exclude_unset=True).keys())},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return RouterResponse.model_validate(r)


@router.delete("/{router_id}")
def delete_router(
    router_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    r = require_visible_router(router_id, current_user, db)
    name = r.name
    log_audit(db, current_user.username, "delete", "router",
              r.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)

    from app.models.alert import Alert
    from app.models.event_log import EventLog
    from app.models.backup import Backup
    from app.models.router_history import RouterHistory
    from app.models.interface_traffic import InterfaceTrafficSample
    from app.models.interface_counter_state import InterfaceCounterState

    db.query(Alert).filter(Alert.router_id == router_id).delete()
    db.query(EventLog).filter(EventLog.router_id == router_id).delete()
    db.query(Backup).filter(Backup.router_id == router_id).delete()
    db.query(RouterHistory).filter(RouterHistory.router_id == router_id).delete()
    db.query(InterfaceTrafficSample).filter(InterfaceTrafficSample.router_id == router_id).delete()
    db.query(InterfaceCounterState).filter(InterfaceCounterState.router_id == router_id).delete()

    db.delete(r)
    db.commit()
    return {"detail": "Router eliminado"}


@router.post("/{router_id}/check")
def check_router_status_endpoint(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(*_VIEW_PERMS)),
):
    r = require_visible_router(router_id, current_user, db)
    was_online = r.is_online
    from app.services.routeros_service import check_router_status
    result = check_router_status(r)
    db.commit()
    db.refresh(r)

    if was_online and not r.is_online:
        from app.models.alert import Alert
        existing = db.query(Alert).filter(
            Alert.router_id == r.id,
            Alert.alert_type == "router_offline",
            Alert.is_resolved == False,
        ).first()
        if not existing:
            from datetime import datetime, timezone
            alert = Alert(
                router_id=r.id,
                alert_type="router_offline",
                severity="critical",
                title=f"{r.name} se desconectó",
                message=f"El router {r.name} dejó de responder (verificación manual).",
            )
            db.add(alert)
            db.commit()

            from app.api.v1.settings import notify
            notify(f"{r.name} se desconectó",
                   f"El router {r.name} dejó de responder (verificación manual).",
                   f"🔴 <b>{r.name} se desconectó</b>\nEl router dejó de responder (verificación manual).")

    elif not was_online and r.is_online:
        from app.models.alert import Alert
        existing = db.query(Alert).filter(
            Alert.router_id == r.id,
            Alert.alert_type == "router_online",
            Alert.is_resolved == False,
        ).first()
        if existing:
            from datetime import datetime, timezone
            existing.is_resolved = True
            existing.resolved_at = datetime.now(timezone.utc)
            existing.resolved_by = current_user.username
            db.commit()

        from app.models.alert import Alert
        alert = Alert(
            router_id=r.id,
            alert_type="router_online",
            severity="info",
            title=f"{r.name} se reconectó",
            message=f"El router {r.name} está nuevamente en línea (verificación manual).",
        )
        db.add(alert)
        db.commit()

        from app.api.v1.settings import notify
        notify(f"{r.name} se reconectó",
               f"El router {r.name} está nuevamente en línea (verificación manual).",
               f"🟢 <b>{r.name} se reconectó</b>\nEl router está nuevamente en línea (verificación manual).")

    return result
