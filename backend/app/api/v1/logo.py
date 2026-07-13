import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_permission
from app.models.user import User
from app.utils.audit import log_audit

router = APIRouter()

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOGO_DIR = os.path.join(_BASE, "static", "logo")

_DEFAULT_LOGO_SVG = r'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 80">
  <rect width="280" height="80" rx="8" fill="#1e293b"/>
  <text x="20" y="52" font-family="Arial,sans-serif" font-size="28" font-weight="bold" fill="#38bdf8">Mikro</text>
  <text x="110" y="52" font-family="Arial,sans-serif" font-size="28" fill="#e2e8f0">Control</text>
</svg>'''

_DEFAULT_FAVICON_SVG = r'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="4" fill="#1e293b"/>
  <text x="4" y="24" font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="#38bdf8">M</text>
</svg>'''

EXT_MAP = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

def _ensure_dir():
    os.makedirs(LOGO_DIR, exist_ok=True)

def _find_logo():
    _ensure_dir()
    for f in sorted(os.listdir(LOGO_DIR)):
        if f.startswith("logo."):
            path = os.path.join(LOGO_DIR, f)
            if os.path.isfile(path):
                return path
    # Auto-crear default si no hay ninguno
    dest = os.path.join(LOGO_DIR, "logo.svg")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(_DEFAULT_LOGO_SVG)
    return dest

def _media_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return EXT_MAP.get(ext, "image/svg+xml")

def _find_favicon():
    _ensure_dir()
    for f in sorted(os.listdir(LOGO_DIR)):
        if f.startswith("favicon."):
            path = os.path.join(LOGO_DIR, f)
            if os.path.isfile(path):
                return path
    # Auto-crear default si no hay ninguno
    dest = os.path.join(LOGO_DIR, "favicon.svg")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(_DEFAULT_FAVICON_SVG)
    return dest

@router.get("/")
def get_logo():
    path = _find_logo()
    if path:
        return FileResponse(path, media_type=_media_type(path))
    raise HTTPException(status_code=404, detail="Logo no encontrado")

@router.get("/favicon")
def get_favicon():
    path = _find_favicon()
    if path:
        return FileResponse(path, media_type=_media_type(path))
    raise HTTPException(status_code=404, detail="Favicon no encontrado")

@router.post("/upload")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    if not file.filename or not file.filename.lower().endswith((".svg", ".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="Formato no soportado. Usá SVG, PNG, JPG o WebP")
    os.makedirs(LOGO_DIR, exist_ok=True)
    for f in os.listdir(LOGO_DIR):
        if f.startswith("logo."):
            os.remove(os.path.join(LOGO_DIR, f))
    ext = os.path.splitext(file.filename)[1].lower()
    dest = os.path.join(LOGO_DIR, f"logo{ext}")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    log_audit(db, current_user.username, "update", "logo", details={"file": f"logo{ext}"}, user_id=current_user.id)
    db.commit()
    return {"url": f"/api/v1/logo/", "filename": f"logo{ext}"}

@router.post("/favicon/upload")
async def upload_favicon(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    if not file.filename or not file.filename.lower().endswith((".svg", ".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="Formato no soportado. Usá SVG, PNG, JPG o WebP")
    os.makedirs(LOGO_DIR, exist_ok=True)
    for f in os.listdir(LOGO_DIR):
        if f.startswith("favicon."):
            os.remove(os.path.join(LOGO_DIR, f))
    ext = os.path.splitext(file.filename)[1].lower()
    dest = os.path.join(LOGO_DIR, f"favicon{ext}")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    log_audit(db, current_user.username, "update", "favicon", details={"file": f"favicon{ext}"}, user_id=current_user.id)
    db.commit()
    return {"url": f"/api/v1/logo/favicon", "filename": f"favicon{ext}"}

def _write_default(name_prefix, content):
    """Escribe un archivo SVG por defecto (inline) en LOGO_DIR."""
    os.makedirs(LOGO_DIR, exist_ok=True)
    # Limpia archivos previos del mismo tipo
    for f in os.listdir(LOGO_DIR):
        if f.startswith(name_prefix + "."):
            os.remove(os.path.join(LOGO_DIR, f))
    dest = os.path.join(LOGO_DIR, f"{name_prefix}.svg")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

@router.post("/favicon/reset")
def reset_favicon(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    _write_default("favicon", _DEFAULT_FAVICON_SVG)
    log_audit(db, current_user.username, "reset", "favicon", user_id=current_user.id)
    db.commit()
    return {"detail": "Favicon restaurado al predeterminado"}

@router.post("/reset")
def reset_logo(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    _write_default("logo", _DEFAULT_LOGO_SVG)
    log_audit(db, current_user.username, "reset", "logo", user_id=current_user.id)
    db.commit()
    return {"detail": "Logo restaurado al predeterminado"}
