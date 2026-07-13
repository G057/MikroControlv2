import os, glob, time, threading, subprocess, shutil
from datetime import datetime
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from app.core.database import get_db, engine, settings
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.api.v1.settings import get_setting, _set

router = APIRouter()

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "backups")
BACKUP_DIR = os.path.normpath(BACKUP_DIR)
_restart_timer = None
_restore_lock = threading.Lock()


def _pg_conn():
    """Extrae host/user/pass/db del DATABASE_URL (postgresql://user:pass@host:port/db)."""
    p = urlparse(settings.DATABASE_URL)
    return {
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "user": p.username or "postgres",
        "password": p.password or "",
        "dbname": p.path.lstrip("/") or "mikrocontrol",
    }


def _pg_env(conn: dict) -> dict:
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    return env


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _list_backup_files():
    _ensure_backup_dir()
    files = []
    for f in sorted(glob.glob(os.path.join(BACKUP_DIR, "*.dump")), reverse=True) + \
             sorted(glob.glob(os.path.join(BACKUP_DIR, "*.sql")), reverse=True):
        st = os.stat(f)
        fname = os.path.basename(f)
        try:
            dt = datetime.strptime(fname.replace("backup_", "").replace(".dump", "").replace(".sql", ""), "%Y%m%d_%H%M%S")
        except ValueError:
            dt = datetime.fromtimestamp(st.st_mtime)
        files.append({
            "filename": fname,
            "size": st.st_size,
            "created_at": dt.isoformat(),
            "created_at_display": dt.strftime("%d/%m/%Y %H:%M:%S"),
        })
    return files


@router.get("/")
def list_backups(current_user: User = Depends(require_permission("settings:view"))):
    return _list_backup_files()


def _do_create_backup() -> dict:
    _ensure_backup_dir()
    conn = _pg_conn()
    fname = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"
    dest = os.path.join(BACKUP_DIR, fname)
    try:
        subprocess.run(
            ["pg_dump", "-h", conn["host"], "-p", conn["port"], "-U", conn["user"],
             "-F", "c", "-f", dest, conn["dbname"]],
            env=_pg_env(conn), check=True, capture_output=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="pg_dump no encontrado. Instalá PostgreSQL client.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error al generar backup: {e.stderr.decode(errors='ignore')[:300]}")
    return {"filename": fname, "size": os.path.getsize(dest), "message": "Backup creado exitosamente"}


@router.post("/create")
def create_backup(current_user: User = Depends(require_permission("settings:edit"))):
    return _do_create_backup()


@router.get("/download/{filename}")
def download_backup(filename: str, current_user: User = Depends(require_permission("settings:view"))):
    _ensure_backup_dir()
    safe = os.path.normpath(os.path.join(BACKUP_DIR, filename))
    if not safe.startswith(BACKUP_DIR) or not os.path.isfile(safe):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(safe, filename=filename, media_type="application/octet-stream")


@router.post("/restore/{filename}")
def restore_backup(filename: str, current_user: User = Depends(require_permission("settings:edit"))):
    global _restart_timer
    acquired = _restore_lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(429, "Ya hay una restauración en progreso")

    try:
        _ensure_backup_dir()
        safe = os.path.normpath(os.path.join(BACKUP_DIR, filename))
        if not safe.startswith(BACKUP_DIR) or not os.path.isfile(safe):
            raise HTTPException(404, "Archivo no encontrado")

        conn = _pg_conn()

        # Close pooled connections before restoring.
        try:
            engine.dispose()
        except Exception:
            pass

        is_sql = filename.endswith(".sql")
        try:
            if is_sql:
                subprocess.run(
                    ["psql", "-h", conn["host"], "-p", conn["port"], "-U", conn["user"],
                     "-d", conn["dbname"], "-f", safe],
                    env=_pg_env(conn), check=True, capture_output=True,
                )
            else:
                subprocess.run(
                    ["pg_restore", "-h", conn["host"], "-p", conn["port"], "-U", conn["user"],
                     "--clean", "--if-exists", "-d", conn["dbname"], safe],
                    env=_pg_env(conn), check=True, capture_output=True,
                )
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="psql/pg_restore no encontrado. Instalá PostgreSQL client.")
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Error al restaurar: {e.stderr.decode(errors='ignore')[:300]}")

        # El pool se reconecta solo en la próxima petición.
        return {"message": "Backup restaurado. La base de datos está disponible nuevamente."}
    finally:
        _restore_lock.release()


@router.delete("/{filename}")
def delete_backup(filename: str, current_user: User = Depends(require_permission("settings:edit"))):
    _ensure_backup_dir()
    safe = os.path.normpath(os.path.join(BACKUP_DIR, filename))
    if not safe.startswith(BACKUP_DIR) or not os.path.isfile(safe):
        raise HTTPException(404, "Archivo no encontrado")
    os.remove(safe)
    return {"message": f"Backup {filename} eliminado"}


@router.post("/delete-bulk")
def delete_backups_bulk(data: dict, current_user: User = Depends(require_permission("settings:edit"))):
    filenames = data.get("filenames", [])
    deleted = []
    not_found = []
    for fname in filenames:
        safe = os.path.normpath(os.path.join(BACKUP_DIR, fname))
        if safe.startswith(BACKUP_DIR) and os.path.isfile(safe):
            os.remove(safe)
            deleted.append(fname)
        else:
            not_found.append(fname)
    return {"message": f"{len(deleted)} backup(s) eliminado(s)", "deleted": deleted, "not_found": not_found}


BACKUP_INTERVAL_KEY = "backup_interval_hours"
BACKUP_SCHEDULE_DAYS_KEY = "backup_schedule_days"
BACKUP_SCHEDULE_TIME_KEY = "backup_schedule_time"
_backup_scheduler_active = False


def _should_run_scheduled(days_str: str, time_str: str) -> bool:
    from datetime import datetime as dt
    now = dt.now()
    if days_str:
        selected = set(d.strip() for d in days_str.split(",") if d.strip())
        if str(now.weekday()) not in selected:
            return False
    if time_str:
        try:
            h, m = time_str.split(":")
            target = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            diff = (now - target).total_seconds()
            if diff < 0 or diff >= 120:
                return False
        except Exception:
            pass
    return True


def _backup_scheduler_loop():
    global _backup_scheduler_active
    _backup_scheduler_active = True
    last = 0
    while True:
        time.sleep(60)
        try:
            from app.core.database import SessionLocal
            db = SessionLocal()
            interval = int(get_setting(db, BACKUP_INTERVAL_KEY, "0"))
            days = get_setting(db, BACKUP_SCHEDULE_DAYS_KEY, "")
            sched_time = get_setting(db, BACKUP_SCHEDULE_TIME_KEY, "03:00")
            db.close()
        except Exception:
            interval = 0
            days = ""
            sched_time = "03:00"

        now = time.time()
        do_backup = False

        if days:
            if now - last >= 3600:
                do_backup = _should_run_scheduled(days, sched_time)
        elif interval > 0:
            if now - last >= interval * 3600:
                do_backup = True

        if do_backup:
            try:
                _do_create_backup()
                last = now
            except Exception:
                pass


def start_backup_scheduler():
    t = threading.Thread(target=_backup_scheduler_loop, daemon=True, name="backup-scheduler")
    t.start()
