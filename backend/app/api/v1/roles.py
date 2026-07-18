from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Literal, Optional
from app.core.database import get_db
from app.core.security import require_permission, get_user_permissions
from app.models.user import User
from app.models.role import Role
from app.core.permissions import PERMISSION_CATALOG, PERMISSION_GROUPS, ALL_PERMISSIONS

router = APIRouter()


def _assert_no_escalation(actor: User, permissions):
    """Un no-admin no puede otorgar permisos que él mismo no posee."""
    if actor.role == "admin":
        return
    actor_perms = set(get_user_permissions(actor))
    escalated = [p for p in permissions if p not in actor_perms]
    if escalated:
        raise HTTPException(
            status_code=403,
            detail=f"No podés otorgar permisos que no tenés: {escalated}",
        )


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    permissions: List[str] = []
    event_categories: List[str] = []
    router_scope: Literal["all", "selected"] = "all"
    router_ids: List[int] = []
    router_group_ids: List[int] = []


class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    event_categories: Optional[List[str]] = None
    router_scope: Optional[Literal["all", "selected"]] = None
    router_ids: Optional[List[int]] = None
    router_group_ids: Optional[List[int]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str
    is_system: bool
    permissions: List[str] = []
    event_categories: List[str] = []
    router_scope: str = "all"
    router_ids: List[int] = []
    router_group_ids: List[int] = []
    user_count: int = 0

    class Config:
        from_attributes = True


class RoleOption(BaseModel):
    id: int
    name: str
    description: str


def _serialize(role: Role, user_count: int) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=role.get_permissions(),
        event_categories=role.get_event_categories(),
        router_scope=role.get_router_scope(),
        router_ids=role.get_router_ids(),
        router_group_ids=role.get_router_group_ids(),
        user_count=user_count,
    )


@router.get("/permissions/catalog")
def permission_catalog(_: User = Depends(require_permission("roles:manage"))):
    return {
        "groups": [
            {"group": g, "permissions": [{"key": k, "label": l, "description": d} for k, l, d in perms]}
            for g, perms in PERMISSION_GROUPS.items()
        ],
        "all": ALL_PERMISSIONS,
    }


@router.get("/options", response_model=List[RoleOption])
def list_assignable_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit")),
):
    roles = db.query(Role).order_by(Role.name).all()
    if current_user.role == "admin":
        return [RoleOption(id=role.id, name=role.name, description=role.description) for role in roles]

    actor_permissions = set(get_user_permissions(current_user))
    return [
        RoleOption(id=role.id, name=role.name, description=role.description)
        for role in roles
        if role.name != "admin" and set(role.get_permissions()).issubset(actor_permissions)
    ]


@router.get("/", response_model=List[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:manage")),
):
    roles = db.query(Role).order_by(Role.is_system.desc(), Role.name).all()
    result = []
    for r in roles:
        user_count = db.query(func.count(User.id)).filter(User.role == r.name).scalar() or 0
        result.append(_serialize(r, user_count))
    return result


@router.post("/", response_model=RoleResponse)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:manage")),
):
    name = data.name.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del rol es requerido")
    if name == "admin":
        raise HTTPException(status_code=400, detail="No se puede crear un rol 'admin'")
    existing = db.query(Role).filter(Role.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un rol con ese nombre")
    invalid = [p for p in data.permissions if p not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Permisos inválidos: {invalid}")
    _assert_no_escalation(current_user, data.permissions)
    role = Role(name=name, description=data.description or "", is_system=False)
    role.set_permissions(data.permissions)
    role.set_event_categories(data.event_categories)
    role.set_router_scope(data.router_scope)
    role.set_router_ids(data.router_ids)
    role.set_router_group_ids(data.router_group_ids)
    db.add(role)
    db.commit()
    return _serialize(role, 0)


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:manage")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    user_count = db.query(func.count(User.id)).filter(User.role == role.name).scalar() or 0
    return _serialize(role, user_count)


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:manage")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if role.is_system:
        raise HTTPException(status_code=400, detail="No se puede modificar un rol de sistema")
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        invalid = [p for p in data.permissions if p not in ALL_PERMISSIONS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Permisos inválidos: {invalid}")
        _assert_no_escalation(current_user, data.permissions)
        role.set_permissions(data.permissions)
    if data.event_categories is not None:
        role.set_event_categories(data.event_categories)
    if data.router_scope is not None:
        role.set_router_scope(data.router_scope)
    if data.router_ids is not None:
        role.set_router_ids(data.router_ids)
    if data.router_group_ids is not None:
        role.set_router_group_ids(data.router_group_ids)
    db.commit()
    user_count = db.query(func.count(User.id)).filter(User.role == role.name).scalar() or 0
    return _serialize(role, user_count)


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:manage")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if role.is_system:
        raise HTTPException(status_code=400, detail="No se puede eliminar un rol de sistema")
    user_count = db.query(func.count(User.id)).filter(User.role == role.name).scalar() or 0
    if user_count > 0:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar: {user_count} usuario(s) usan este rol")
    db.delete(role)
    db.commit()
    return {"detail": "Rol eliminado"}
