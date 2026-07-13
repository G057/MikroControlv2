from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.template import ConfigTemplate
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse
from app.utils.audit import log_audit

router = APIRouter()


@router.get("/", response_model=List[TemplateResponse])
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [TemplateResponse.model_validate(t) for t in db.query(ConfigTemplate).order_by(ConfigTemplate.name).all()]


@router.post("/", response_model=TemplateResponse)
def create_template(
    data: TemplateCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    template = ConfigTemplate(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    log_audit(db, current_user.username, "create", "template",
              template.id, template.name, {"category": template.category},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return TemplateResponse.model_validate(t)


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    data: TemplateUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    t = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(t, key, value)
    db.commit()
    db.refresh(t)
    log_audit(db, current_user.username, "update", "template",
              t.id, t.name, {"fields": list(data.model_dump(exclude_unset=True).keys())},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return TemplateResponse.model_validate(t)


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    t = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    name = t.name
    log_audit(db, current_user.username, "delete", "template",
              t.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.delete(t)
    db.commit()
    return {"detail": "Plantilla eliminada"}
