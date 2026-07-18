import time, threading, os, glob, logging
from datetime import datetime
from app.core.database import SessionLocal
from app.models.router import Router
from app.models.backup import Backup
from app.api.v1.settings import get_setting, DEFAULTS
from app.core.backup_utils import BACKUP_DIR, should_run_backup_schedule

logger = logging.getLogger(__name__)

BACKUP_INTERVAL_KEY = "router_backup_interval_hours"
BACKUP_SCHEDULE_DAYS_KEY = "router_backup_schedule_days"
BACKUP_SCHEDULE_TIME_KEY = "router_backup_schedule_time"
BACKUP_TYPE_KEY = "router_backup_type"
BACKUP_RETENTION_DAYS_KEY = "router_backup_retention_days"
BACKUP_RETENTION_COUNT_KEY = "router_backup_retention_count"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_RETENTION_COUNT = 60
DEFAULT_BACKUP_TYPE = "export"


def _router_backup_dir():
    return BACKUP_DIR


def _cleanup_old_backups():
    days = DEFAULT_RETENTION_DAYS
    count = DEFAULT_RETENTION_COUNT
    try:
        db = SessionLocal()
        try:
            days = int(get_setting(db, BACKUP_RETENTION_DAYS_KEY, str(DEFAULT_RETENTION_DAYS)))
            count = int(get_setting(db, BACKUP_RETENTION_COUNT_KEY, str(DEFAULT_RETENTION_COUNT)))
        finally:
            db.close()
    except Exception:
        pass

    if days <= 0 and count <= 0:
        return

    backup_dir = _router_backup_dir()
    files = glob.glob(os.path.join(backup_dir, "*.rsc")) + glob.glob(os.path.join(backup_dir, "*.backup"))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        return
    files.sort(key=os.path.getmtime)

    now_ts = time.time()
    if days > 0:
        cutoff = now_ts - days * 86400
        for f in list(files):
            if os.path.getmtime(f) < cutoff:
                try:
                    os.remove(f)
                    files.remove(f)
                    logger.info("Router backup antiguo eliminado (retención %sd): %s", days, os.path.basename(f))
                except OSError as e:
                    logger.warning("No se pudo eliminar %s: %s", f, e)

    if count > 0 and len(files) > count:
        for f in files[:len(files) - count]:
            try:
                os.remove(f)
                logger.info("Router backup antiguo eliminado (máx %s): %s", count, os.path.basename(f))
            except OSError as e:
                logger.warning("No se pudo eliminar %s: %s", f, e)

    # limpiar registros huérfanos en BD
    try:
        db = SessionLocal()
        try:
            existing = set(os.listdir(_router_backup_dir()))
            orphans = db.query(Backup).all()
            for b in orphans:
                if b.filename not in existing:
                    db.delete(b)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _scheduler_loop():
    while True:
        time.sleep(60)
        try:
            db = SessionLocal()
            try:
                interval = int(get_setting(db, BACKUP_INTERVAL_KEY, DEFAULTS.get(BACKUP_INTERVAL_KEY, "6")))
                days_str = get_setting(db, BACKUP_SCHEDULE_DAYS_KEY, "")
                sched_time = get_setting(db, BACKUP_SCHEDULE_TIME_KEY, "03:00")
                backup_type = get_setting(db, BACKUP_TYPE_KEY, DEFAULT_BACKUP_TYPE)
            finally:
                db.close()
        except Exception:
            interval = 0
            days_str = ""
            sched_time = "03:00"
            backup_type = DEFAULT_BACKUP_TYPE

        try:
            db = SessionLocal()
            try:
                latest = db.query(Backup.created_at).order_by(Backup.created_at.desc()).limit(1).scalar()
            finally:
                db.close()
        except Exception:
            latest = None
        latest_ts = latest.timestamp() if latest else 0
        now = time.time()
        do_backup = False

        if days_str:
            # A database record is a durable daily marker across restarts.
            if not latest or datetime.fromtimestamp(latest_ts).date() != datetime.now().date():
                do_backup = _should_run(days_str, sched_time)
        elif interval > 0:
            if now - latest_ts >= interval * 3600:
                do_backup = True

        if do_backup:
            try:
                _backup_all_routers(backup_type)
                _cleanup_old_backups()
            except Exception as e:
                logger.error("Error en respaldo automático de routers: %s", e)


def _should_run(days_str: str, time_str: str) -> bool:
    return should_run_backup_schedule(days_str, time_str)


def _backup_all_routers(backup_type: str):
    from app.services.routeros_service import create_router_backup
    db = SessionLocal()
    try:
        routers = db.query(Router).filter(Router.is_online == True).all()
        for r in routers:
            try:
                create_router_backup(r, backup_type)
                logger.info("Backup automático creado para %s", r.name)
            except Exception as e:
                logger.error("Error en backup de %s: %s", r.name, e)
    finally:
        db.close()


def start_router_backup_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="router-backup-scheduler")
    t.start()
    logger.info("Programador de respaldos de routers iniciado")
