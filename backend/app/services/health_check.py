import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.models.router import Router
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_health_thread = None
_stop_event = threading.Event()

# Cantidad máxima de routers consultados en paralelo por ciclo.
_MAX_WORKERS = 10


def _probe_router(snapshot: dict) -> dict:
    """Ejecuta el I/O de red contra un router (sin tocar la BD). Se corre en un
    hilo del pool, por eso recibe un snapshot de datos ya extraídos y no el
    objeto ORM (las Session de SQLAlchemy no son thread-safe)."""
    from app.services.routeros_service import RouterOSConnection
    from app.core.crypto import decrypt_secret

    result = {"router_id": snapshot["id"], "ok": False, "error": None,
              "resources": None, "health": None}
    conn = RouterOSConnection(
        host=snapshot["ip_address"],
        port=snapshot["access_port"],
        username=snapshot["api_username"],
        password=decrypt_secret(snapshot["api_password_encrypted"] or ""),
        use_ssl=snapshot["use_ssl"],
    )
    try:
        conn.connect()
        resources = conn.command("/system/resource/print")
        result["resources"] = resources
        if resources:
            result["ok"] = True
            try:
                result["health"] = conn.command("/system/health/print")
            except Exception:
                result["health"] = None
        else:
            result["error"] = "Respuesta vacía del router"
    except Exception as e:
        result["error"] = str(e)
    finally:
        conn.close()
    return result


def _check_all_routers():
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        now = datetime.now(timezone.utc)
        if not routers:
            return

        # Fase 1: consultar los routers en paralelo (solo red, sin BD).
        snapshots = [{
            "id": r.id,
            "ip_address": r.ip_address,
            "access_port": r.access_port,
            "api_username": r.api_username,
            "api_password_encrypted": r.api_password_encrypted,
            "use_ssl": r.use_ssl,
        } for r in routers]
        router_by_id = {r.id: r for r in routers}

        max_workers = min(_MAX_WORKERS, len(snapshots))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="health-probe") as ex:
            results = list(ex.map(_probe_router, snapshots))

        # Fase 2: aplicar resultados a la BD de forma serial (un solo hilo).
        for res in results:
            router = router_by_id.get(res["router_id"])
            if not router:
                continue
            if res["ok"]:
                _apply_online(db, router, now, res["resources"], res["health"])
            else:
                _handle_offline(db, router, now, res["error"] or "Sin respuesta")

        db.commit()
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        db.rollback()
    finally:
        db.close()


def _apply_online(db, router, now, resources, health):
    was_offline = not router.is_online
    router.is_online = True
    router.last_seen = now
    r = resources[0]
    try:
        router.cpu_usage = float(r.get("cpu-load", 0))
    except (ValueError, TypeError):
        router.cpu_usage = 0
    try:
        from app.services.routeros_service import _parse_memory_mb
        total_mb = _parse_memory_mb(r.get("total-memory", "0"))
        free_mb = _parse_memory_mb(r.get("free-memory", "0"))
        if total_mb > 0:
            router.ram_usage = round(((total_mb - free_mb) / total_mb) * 100, 1)
    except Exception:
        pass
    try:
        router.hdd_free = round(int(r.get("free-hdd-space", "0")) / 1048576, 1)
        router.hdd_total = round(int(r.get("total-hdd-space", "0")) / 1048576, 1)
    except (ValueError, TypeError):
        pass
    router.uptime = r.get("uptime", "")
    router.routeros_version = r.get("version", "")
    if not router.model:
        board = r.get("board-name", "") or r.get("platform", "")
        if board:
            router.model = board

    if health:
        for item in health:
            name = item.get("name", "")
            value = item.get("value", "")
            if name == "temperature" and value:
                try:
                    router.temperature = float(value)
                except (ValueError, TypeError):
                    pass
            elif name == "voltage" and value:
                try:
                    router.voltage = float(value)
                except (ValueError, TypeError):
                    pass

    if was_offline:
        # El router volvió: resolver la alerta de desconexión (el problema
        # terminó) y limpiar notificaciones previas de reconexión activas.
        db.query(Alert).filter(
            Alert.router_id == router.id,
            Alert.alert_type.in_(["router_offline", "router_online"]),
            Alert.is_resolved == False,
        ).update({
            "is_resolved": True,
            "resolved_at": now,
            "resolved_by": "system",
            "resolution_comment": "El router volvió a estar en línea",
        }, synchronize_session=False)

        # Notificación informativa de reconexión (ya resuelta: no es un
        # problema activo, no debe contar como alerta abierta).
        _create_alert(db, router.id, "router_online", "info",
                      f"{router.name} se reconectó",
                      f"El router {router.name} está nuevamente en línea",
                      resolved=True)


def _handle_offline(db, router, now, error_msg):
    was_online = router.is_online
    router.is_online = False
    router.last_seen = now

    if was_online:
        _create_alert(db, router.id, "router_offline", "critical",
                      f"{router.name} se desconectó",
                      f"El router {router.name} dejó de responder. Error: {error_msg}")
    else:
        existing = db.query(Alert).filter(
            Alert.router_id == router.id,
            Alert.alert_type == "router_offline",
            Alert.is_resolved == False,
        ).first()
        if not existing:
            _create_alert(db, router.id, "router_offline", "critical",
                          f"{router.name} offline",
                          f"El router {router.name} no responde. Error: {error_msg}")


def _create_alert(db, router_id, alert_type, severity, title, message, resolved=False):
    from app.api.v1.settings import get_setting
    if get_setting(db, "health_alerts_enabled", "true") != "true":
        return

    existing = db.query(Alert).filter(
        Alert.router_id == router_id,
        Alert.alert_type == alert_type,
        Alert.is_resolved == False,
    ).first()
    if existing:
        return

    from datetime import datetime, timezone
    alert = Alert(
        router_id=router_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        is_resolved=resolved,
        resolved_at=datetime.now(timezone.utc) if resolved else None,
        resolved_by="system" if resolved else None,
    )
    db.add(alert)
    try:
        db.flush()
    except Exception:
        db.rollback()
        return

    from app.api.v1.settings import notify
    icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "ℹ️"
    tg_msg = f"{icon} <b>{title}</b>\n{message}"
    notify(title, message, tg_msg, severity)


def _run_loop():
    while not _stop_event.is_set():
        try:
            _check_all_routers()
        except Exception as e:
            logger.error(f"Health check loop error: {e}")
        from app.api.v1.settings import get_interval
        interval = get_interval("health_check_interval", 60)
        _stop_event.wait(interval)


def start_health_checker():
    global _health_thread
    if _health_thread and _health_thread.is_alive():
        return
    _stop_event.clear()
    _health_thread = threading.Thread(target=_run_loop, daemon=True, name="health-checker")
    _health_thread.start()
    logger.info("Health checker started (interval: 5 min)")


def stop_health_checker():
    _stop_event.set()
