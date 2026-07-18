from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_permission, get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.utils.audit import log_audit
from app.core.user_ops import (
    validate_password_strength, assert_can_assign_role, delete_user_record,
)

router = APIRouter()


def _is_last_admin(db: Session, user: User) -> bool:
    if user.role != "admin":
        return False
    admin_count = db.query(User).filter(User.role == "admin").count()
    return admin_count <= 1


@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:view")),
):
    users = db.query(User).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/", response_model=UserResponse)
def create_user(
    data: UserCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit")),
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username ya existe")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email ya existe")
    validate_password_strength(data.password)
    assert_can_assign_role(current_user, data.role, db)

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        is_active=data.is_active,
        session_timeout_minutes=data.session_timeout_minutes,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(db, current_user.username, "create", "user",
              user.id, user.username, {"role": user.role, "email": user.email},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "username" in update_data and update_data["username"] != user.username:
        existing = db.query(User).filter(
            User.username == update_data["username"], User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username ya existe")
    if "email" in update_data and update_data["email"] != user.email:
        existing = db.query(User).filter(
            User.email == update_data["email"], User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email ya existe")

    new_role = update_data.get("role")
    if new_role is not None and new_role != user.role:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No podés cambiar tu propio rol")
        assert_can_assign_role(current_user, new_role, db)
        if user.role == "admin" and _is_last_admin(db, user):
            raise HTTPException(status_code=400, detail="No podés cambiar el rol del último administrador")

    if "is_active" in update_data and update_data["is_active"] is False:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No podés desactivar tu propia cuenta")
        if _is_last_admin(db, user):
            raise HTTPException(status_code=400, detail="No podés desactivar al último administrador")

    if "password" in update_data and update_data["password"]:
        validate_password_strength(update_data["password"])
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        user.token_version = (user.token_version or 0) + 1
    else:
        update_data.pop("password", None)

    if (
        "session_timeout_minutes" in update_data
        and update_data["session_timeout_minutes"] != user.session_timeout_minutes
    ):
        user.token_version = (user.token_version or 0) + 1

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    log_audit(db, current_user.username, "update", "user",
              user.id, user.username, {"fields": list(data.model_dump(exclude_unset=True).keys())},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="No podés eliminarte a vos mismo")
    if _is_last_admin(db, user):
        raise HTTPException(status_code=400, detail="No podés eliminar al último administrador")
    name = user.username
    log_audit(db, current_user.username, "delete", "user",
              user.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    delete_user_record(db, user)
    db.commit()
    return {"detail": "Usuario eliminado"}
