from datetime import datetime, timezone

from app.models.alert import Alert
from app.models.monitoring import RouterConnectivityState
from app.services.event_pipeline import NormalizedEvent, ingest_event


def _setting(db, key, default):
    from app.api.v1.settings import get_setting
    try:
        return max(1, int(get_setting(db, key, str(default))))
    except (TypeError, ValueError):
        return default


def apply_probe_result(db, router, ok: bool, error: str | None = None, now=None):
    """The sole authority for Router.is_online transitions."""
    now = now or datetime.now(timezone.utc)
    state = db.get(RouterConnectivityState, router.id)
    if not state:
        state = RouterConnectivityState(router_id=router.id)
        db.add(state)
        db.flush()
    before = state.current_state
    state.last_check_at = now
    transition = None
    if ok:
        state.consecutive_failures = 0
        state.consecutive_successes += 1
        state.last_success_at = now
        needed = _setting(db, "health_successes_to_online", 2)
        if state.current_state == "OFFLINE":
            state.current_state = "RECOVERING"
        if state.consecutive_successes >= needed and state.current_state != "ONLINE":
            state.current_state = "ONLINE"
            state.last_state_change_at = now
            router.is_online = True
            router.last_seen = now
            if before in ("OFFLINE", "RECOVERING"):
                transition = "online"
                offline = db.query(Alert).filter(Alert.router_id == router.id, Alert.alert_type == "router_offline",
                                                   Alert.is_resolved == False).first()
                event, _, _, _ = ingest_event(db, NormalizedEvent(router.id, router.name, "health_check",
                    "health,recovery", f"{router.name} se reconectó", "recovery", "router_online",
                    event_timestamp=now, correlation_id=f"{router.id}:router_offline"), create_alert=False)
                if offline:
                    offline.is_resolved = True
                    offline.resolved_at = now
                    offline.resolution_event_id = event.id
        return transition

    state.consecutive_successes = 0
    state.consecutive_failures += 1
    state.last_failure_at = now
    needed = _setting(db, "health_failures_to_offline", 3)
    if state.consecutive_failures < needed:
        state.current_state = "SUSPECTED_OFFLINE"
        return None
    if state.current_state != "OFFLINE":
        state.current_state = "OFFLINE"
        state.offline_since = now
        state.last_state_change_at = now
        router.is_online = False
        transition = "offline"
        ingest_event(db, NormalizedEvent(router.id, router.name, "health_check", "health,critical",
            f"{router.name} se desconectó. {error or 'Sin respuesta'}", "critical", "router_offline",
            event_timestamp=now, correlation_id=f"{router.id}:router_offline"))
    return transition
