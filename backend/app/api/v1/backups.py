from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.backup import Backup
from app.models.router import Router
from app.schemas.template import BackupResponse
from app.utils.audit import log_audit
from app.core.router_access import get_visible_router_ids, require_visible_router
from app.core.backup_utils import BACKUP_DIR

router = APIRouter()


def _backup_in_scope(backup: Backup, current_user: User, db: Session) -> bool:
    """El backup es visible si su router está dentro del alcance del usuario."""
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is None:
        return True
    return backup.router_id in visible_ids


def _backup_file_path(file_path: str) -> str:
    backup_dir = os.path.realpath(BACKUP_DIR)
    real = os.path.realpath(file_path)
    try:
        if os.path.commonpath([real, backup_dir]) != backup_dir:
            raise HTTPException(status_code=400, detail="Ruta de backup inválida")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta de backup inválida")
    return real


@router.get("/", response_model=List[BackupResponse])
def list_backups(
    router_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:backup")),
):
    query = db.query(Backup)
    if router_id:
        query = query.filter(Backup.router_id == router_id)
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None:
        query = query.filter(Backup.router_id.in_(visible_ids))
    return [BackupResponse.model_validate(b) for b in query.order_by(Backup.created_at.desc()).limit(200).all()]


@router.post("/backup/{router_id}")
def create_backup(
    router_id: int,
    body: dict = Body(...),
    req: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:backup")),
):
    backup_type = body.get("backup_type", "binary")
    r = require_visible_router(router_id, current_user, db)

    from app.services.routeros_service import create_router_backup
    result = create_router_backup(r, backup_type)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Error al crear backup"))
    log_audit(db, current_user.username, "create", "backup",
              None, r.name, {"backup_type": backup_type, "router_id": router_id},
              current_user.id, req.client.host if req and req.client else None)
    db.commit()
    return result


@router.post("/restore/{backup_id}")
def restore_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:backup")),
):
    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    if not _backup_in_scope(backup, current_user, db):
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    raise HTTPException(status_code=501, detail="La restauración de backups de routers todavía no está implementada")


@router.get("/{backup_id}/download")
def download_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:backup")),
):
    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    if not _backup_in_scope(backup, current_user, db):
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    if not backup.file_path or not os.path.isfile(backup.file_path):
        raise HTTPException(status_code=404, detail="Archivo de backup no encontrado en disco")
    real = _backup_file_path(backup.file_path)
    return FileResponse(
        path=real,
        filename=backup.filename,
        media_type="application/octet-stream",
    )


@router.delete("/{backup_id}")
def delete_backup(
    backup_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:backup")),
):
    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    if not _backup_in_scope(backup, current_user, db):
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    if backup.file_path:
        real = _backup_file_path(backup.file_path)
        if os.path.exists(real):
            try:
                os.remove(real)
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"No se pudo eliminar el archivo de backup: {exc}")
    name = backup.filename
    log_audit(db, current_user.username, "delete", "backup",
              backup.id, name, user_id=current_user.id,
              ip_address=req.client.host if req.client else None)
    db.delete(backup)
    db.commit()
    return {"detail": "Backup eliminado"}
