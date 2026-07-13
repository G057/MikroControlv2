from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.router import Router
from app.models.role import Role


def load_role_router_scope(role_name: str, db: Session) -> dict:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        return {"scope": "all", "router_ids": [], "group_ids": []}
    return {
        "scope": role.get_router_scope(),
        "router_ids": role.get_router_ids(),
        "group_ids": role.get_router_group_ids(),
    }


def get_visible_router_ids(current_user: User, db: Session):
    """Devuelve None si el usuario ve todos los routers, o un set de ids visibles."""
    if current_user.role == "admin":
        return None
    scope = load_role_router_scope(current_user.role, db)
    if scope["scope"] == "all":
        return None
    ids = set(scope["router_ids"])
    group_ids = set(scope["group_ids"])
    if group_ids:
        for r in db.query(Router.id, Router.group_id).all():
            if r.group_id is not None and r.group_id in group_ids:
                ids.add(r.id)
    return ids


def require_visible_router(router_id: int, current_user: User, db: Session) -> Router:
    """Igual que buscar el router, pero lanza 404 si está fuera del alcance del rol."""
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    ids = get_visible_router_ids(current_user, db)
    if ids is not None and r.id not in ids:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    return r
