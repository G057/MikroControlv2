from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.router import RouterGroup, RouterTag
from app.schemas.router import GroupCreate, GroupResponse, TagCreate, TagResponse
from app.utils.audit import log_audit

router = APIRouter()


@router.get("/", response_model=List[GroupResponse])
def list_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    groups = db.query(RouterGroup).order_by(RouterGroup.name).all()
    return [GroupResponse.model_validate(g) for g in groups]


@router.post("/", response_model=GroupResponse)
def create_group(
    data: GroupCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("groups:edit")),
):
    group = RouterGroup(name=data.name, description=data.description, color=data.color)
    db.add(group)
    db.commit()
    db.refresh(group)
    log_audit(db, current_user.username, "create", "group",
              group.id, group.name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.commit()
    return GroupResponse.model_validate(group)


@router.put("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    data: GroupCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("groups:edit")),
):
    group = db.query(RouterGroup).filter(RouterGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    group.name = data.name
    group.description = data.description
    group.color = data.color
    db.commit()
    db.refresh(group)
    log_audit(db, current_user.username, "update", "group",
              group.id, group.name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.commit()
    return GroupResponse.model_validate(group)


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("groups:edit")),
):
    group = db.query(RouterGroup).filter(RouterGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    name = group.name
    log_audit(db, current_user.username, "delete", "group",
              group.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.delete(group)
    db.commit()
    return {"detail": "Grupo eliminado"}


@router.get("/tags/", response_model=List[TagResponse])
def list_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [TagResponse.model_validate(t) for t in db.query(RouterTag).all()]


@router.post("/tags/", response_model=TagResponse)
def create_tag(
    data: TagCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("groups:edit")),
):
    tag = RouterTag(name=data.name, color=data.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    log_audit(db, current_user.username, "create", "tag",
              tag.id, tag.name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.commit()
    return TagResponse.model_validate(tag)


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("groups:edit")),
):
    tag = db.query(RouterTag).filter(RouterTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    name = tag.name
    log_audit(db, current_user.username, "delete", "tag",
              tag.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.delete(tag)
    db.commit()
    return {"detail": "Tag eliminado"}
