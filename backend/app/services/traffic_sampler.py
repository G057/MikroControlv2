import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from app.core.database import SessionLocal
from app.models.router import Router
from app.models.interface_traffic import InterfaceTraffic
from app.models.interface_counter_state import InterfaceCounterState

logger = logging.getLogger(__name__)

_traffic_thread = None
_stop_event = threading.Event()
_last_purge = 0.0
_PURGE_INTERVAL = 3600
# Contador que se aleja demasiado del intervalo esperado -> descartar el delta
# (evita picos falsos tras huecos largos, reinicios o cambios de reloj).
_MAX_ELAPSED = 3600

# (router_id, interface) -> (rx_byte, tx_byte, wall_ts_utc) de la última muestra.
# Se calcula el delta usando reloj de pared (wall clock) para que el baseline
# siga siendo válido entre reinicios. Se hidrata desde la BD al arrancar y se
# persiste en interface_counter_state tras cada muestra.
_last_counters = {}
_counters_loaded = False


def _load_counters(db):
    """Hidrata _last_counters desde la BD (una sola vez tras el arranque)."""
    global _counters_loaded
    if _counters_loaded:
        return
    try:
        for st in db.query(InterfaceCounterState).all():
            ts = st.updated_at
            if ts is not None and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            _last_counters[(st.router_id, st.interface)] = (st.rx_byte, st.tx_byte, ts)
        _counters_loaded = True
        logger.info(f"Baseline de tráfico cargado: {len(_last_counters)} interfaces")
    except Exception as e:
        logger.warning(f"No se pudo cargar el baseline de tráfico: {e}")


def _persist_counter(db, router_id, name, rx, tx, now):
    """Guarda/actualiza el último contador crudo para sobrevivir reinicios."""
    st = (
        db.query(InterfaceCounterState)
        .filter(
            InterfaceCounterState.router_id == router_id,
            InterfaceCounterState.interface == name,
        )
        .first()
    )
    if st is None:
        db.add(InterfaceCounterState(
            router_id=router_id, interface=name, rx_byte=rx, tx_byte=tx, updated_at=now,
        ))
    else:
        st.rx_byte = rx
        st.tx_byte = tx
        st.updated_at = now


def _to_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _purge_old_traffic(db):
    """Acota el crecimiento de interface_traffic según traffic_retention_days."""
    global _last_purge
    now = time.time()
    if now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    try:
        from app.api.v1.settings import get_setting
        days = int(get_setting(db, "traffic_retention_days", "7") or "7")
        if days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = db.query(InterfaceTraffic).filter(
            InterfaceTraffic.timestamp < cutoff
        ).delete(synchronize_session=False)
        db.commit()
        if deleted:
            logger.info(f"Retención: {deleted} muestras de tráfico anteriores a {days} días eliminadas")
    except Exception as e:
        logger.error(f"Error purgando tráfico antiguo: {e}")
        db.rollback()


def _sample_all():
    db = SessionLocal()
    try:
        _load_counters(db)
        routers = db.query(Router).filter(Router.is_online == True).all()
        now = datetime.now(timezone.utc)
        for router in routers:
            try:
                _sample_router(db, router, now)
            except Exception as e:
                logger.warning(f"Traffic sample failed for {router.name}: {e}")
        db.commit()
        _purge_old_traffic(db)
    except Exception as e:
        logger.error(f"Error in traffic sampler: {e}")
        db.rollback()
    finally:
        db.close()


def _sample_router(db, router, now):
    from app.services.routeros_service import _get_connection
    conn = _get_connection(router)
    conn.connect()
    try:
        interfaces = conn.command("/interface/print")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not interfaces:
        return

    for iface in interfaces:
        name = iface.get("name", "")
        if not name:
            continue
        rx = _to_int(iface.get("rx-byte", 0))
        tx = _to_int(iface.get("tx-byte", 0))
        key = (router.id, name)
        prev = _last_counters.get(key)
        _last_counters[key] = (rx, tx, now)
        _persist_counter(db, router.id, name, rx, tx, now)
        if not prev:
            continue  # primera muestra: sembrar, sin delta
        prev_rx, prev_tx, prev_ts = prev
        if prev_ts is None:
            continue
        elapsed = (now - prev_ts).total_seconds()
        # Delta inválido (mismo instante) o hueco demasiado grande -> descartar.
        if elapsed <= 0 or elapsed > _MAX_ELAPSED:
            continue
        rx_delta = rx - prev_rx
        tx_delta = tx - prev_tx
        # Contador reiniciado (reboot / clear-counters) -> descartar el delta.
        if rx_delta < 0:
            rx_delta = 0
        if tx_delta < 0:
            tx_delta = 0
        db.add(InterfaceTraffic(
            router_id=router.id,
            interface=name,
            rx_bps=round((rx_delta * 8) / elapsed, 2),
            tx_bps=round((tx_delta * 8) / elapsed, 2),
            timestamp=now,
        ))


def _run_loop():
    while not _stop_event.is_set():
        try:
            _sample_all()
        except Exception as e:
            logger.error(f"Traffic sampler loop error: {e}")
        from app.api.v1.settings import get_interval
        interval = get_interval("traffic_fetch_interval", 60)
        _stop_event.wait(interval)


def start_traffic_sampler():
    global _traffic_thread
    if _traffic_thread and _traffic_thread.is_alive():
        return
    _stop_event.clear()
    _traffic_thread = threading.Thread(target=_run_loop, daemon=True, name="traffic-sampler")
    _traffic_thread.start()
    logger.info("Interface traffic sampler started (interval: 60s)")


def stop_traffic_sampler():
    _stop_event.set()
