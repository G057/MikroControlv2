from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user, require_permission, require_any_permission
from app.core.permissions import ROUTER_VIEW_PERMS
from app.models.user import User
from app.models.inventory import InventoryItem
from app.schemas.inventory import InventoryCreate, InventoryUpdate, InventoryResponse
from app.utils.audit import log_audit

router = APIRouter()


@router.get("/", response_model=List[InventoryResponse])
def list_inventory(
    item_type: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(*ROUTER_VIEW_PERMS)),
):
    query = db.query(InventoryItem)
    if item_type:
        query = query.filter(InventoryItem.item_type == item_type)
    if status:
        query = query.filter(InventoryItem.status == status)
    if search:
        sf = f"%{search}%"
        query = query.filter(
            (InventoryItem.name.ilike(sf)) |
            (InventoryItem.serial_number.ilike(sf)) |
            (InventoryItem.ip_address.ilike(sf))
        )
    return [InventoryResponse.model_validate(i) for i in query.order_by(InventoryItem.name).all()]


@router.post("/", response_model=InventoryResponse)
def create_inventory_item(
    data: InventoryCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    item = InventoryItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    log_audit(db, current_user.username, "create", "inventory",
              item.id, item.name, {"type": item.item_type},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return InventoryResponse.model_validate(item)


@router.put("/{item_id}", response_model=InventoryResponse)
def update_inventory_item(
    item_id: int,
    data: InventoryUpdate,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    log_audit(db, current_user.username, "update", "inventory",
              item.id, item.name, {"fields": list(data.model_dump(exclude_unset=True).keys())},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return InventoryResponse.model_validate(item)


@router.delete("/{item_id}")
def delete_inventory_item(
    item_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:edit")),
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    name = item.name
    log_audit(db, current_user.username, "delete", "inventory",
              item.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.delete(item)
    db.commit()
    return {"detail": "Item eliminado"}
