import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.models.router import Router
from app.services.connectivity import apply_probe_result

logger = logging.getLogger(__name__)

_health_thread = None
_stop_event = threading.Event()

# Cantidad máxima de routers consultados en paralelo por ciclo.
_MAX_WORKERS = 10


def _probe_router(snapshot: dict) -> dict:
    """Ejecuta el I/O de red contra un router (sin tocar la BD). Se corre en un
    hilo del pool, por eso recibe un snapshot de datos ya extraídos y no el
    objeto ORM (las Session de SQLAlchemy no son thread-safe)."""
    from app.services.routeros_service import RouterOSConnection, shared_router_connection
    from app.core.crypto import decrypt_secret

    result = {"router_id": snapshot["id"], "ok": False, "error": None,
              "resources": None, "health": None}
    try:
        fingerprint = (snapshot["ip_address"], snapshot["access_port"], snapshot["api_username"],
                       snapshot["api_password_encrypted"], snapshot["use_ssl"])
        def factory():
            return RouterOSConnection(
                host=snapshot["ip_address"], port=snapshot["access_port"], username=snapshot["api_username"],
                password=decrypt_secret(snapshot["api_password_encrypted"] or ""), use_ssl=snapshot["use_ssl"],
            )
        with shared_router_connection(snapshot["id"], fingerprint, factory) as conn:
            resources = conn.command("/system/resource/print")
            result["resources"] = resources
            if resources:
                services = conn.command("/ip/service/print")
                expected_name = "api-ssl" if snapshot["use_ssl"] else "api"
                api_service = next((service for service in services if service.get("name") == expected_name), None)
                if api_service and api_service.get("disabled") == "true":
                    # RouterOS keeps existing API sessions alive after the service
                    # is disabled. Detect it explicitly and force re-authentication.
                    conn.close()
                    result["error"] = f"Servicio RouterOS {expected_name} deshabilitado"
                    return result
                result["ok"] = True
                try:
                    result["health"] = conn.command("/system/health/print")
                except Exception:
                    result["health"] = None
            else:
                result["error"] = "Respuesta vacía del router"
    except Exception as e:
        result["error"] = str(e)
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
        recovered_router_ids = []
        for res in results:
            router = router_by_id.get(res["router_id"])
            if not router:
                continue
            if res["ok"]:
                if _apply_online(db, router, now, res["resources"], res["health"]) == "online":
                    recovered_router_ids.append(router.id)
            else:
                _handle_offline(db, router, now, res["error"] or "Sin respuesta")

        db.commit()
        # Remote UDP Syslog cannot traverse the uplink that just failed. Once
        # RouterOS API is available again, ingest its local log buffer once.
        from app.services.log_fetcher import recover_logs
        for router_id in recovered_router_ids:
            try:
                recover_logs(router_id, "connectivity_recovery")
            except Exception as exc:
                logger.warning("No se pudieron recuperar logs de router %s tras reconexión: %s", router_id, exc)
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        db.rollback()
    finally:
        db.close()


def _apply_online(db, router, now, resources, health):
    # Availability is committed only by the persistent state machine below.
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

    return apply_probe_result(db, router, True, now=now)

def _handle_offline(db, router, now, error_msg):
    apply_probe_result(db, router, False, error_msg, now)


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
