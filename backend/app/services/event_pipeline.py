"""Single, idempotent write path for router events and notifications."""
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from sqlalchemy.exc import IntegrityError

from app.models.alert import Alert
from app.models.event_log import EventLog
from app.models.monitoring import Notification

logger = logging.getLogger(__name__)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", value or "")).strip()


def normalize_topics(topics: str) -> str:
    return ",".join(sorted(filter(None, (_clean(part).lower() for part in (topics or "").split(",")))))


def normalize_message(message: str) -> str:
    return _clean(message).lower()


def classify(topics: str, message: str, severity: str | None = None) -> tuple[str, str]:
    topic_set = set(normalize_topics(topics).split(","))
    text = normalize_message(message)
    if "dhcp" in topic_set and "rogue" in text:
        return "dhcp_rogue", severity or "warning"
    if "interface" in topic_set and "down" in text:
        return "interface_down", severity or "warning"
    if "interface" in topic_set and "up" in text:
        return "interface_up", "recovery"
    if "alerta" in text and ("caida" in text or "caída" in text):
        return "ping_loss", severity or "warning"
    if "phase1 negotiation failed" in text:
        return "vpn_down", severity or "critical"
    if "detected conflict by arp response" in text:
        return "arp_conflict", severity if severity in ("critical", "warning") else "warning"
    if "account" in topic_set and ("failure" in text or "failed" in text):
        return "login_failure", severity or "warning"
    if "critical" in topic_set or "error" in topic_set:
        return "unclassified", severity or "critical"
    if "warning" in topic_set:
        return "unclassified", severity or "warning"
    return "unclassified", severity or "info"


@dataclass
class NormalizedEvent:
    router_id: int
    router_name: str
    source: str
    topics: str
    message: str
    severity: str | None = None
    event_type: str | None = None
    ros_time: str = ""
    event_timestamp: datetime | None = None
    received_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_message: str = ""
    correlation_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def normalized(self):
        topics = normalize_topics(self.topics)
        message = normalize_message(self.message)
        event_type, severity = classify(topics, message, self.severity)
        self.event_type = self.event_type or event_type
        self.severity = self.severity or severity
        self.topics = topics
        self.message = _clean(self.message)[:4000]
        self.raw_message = (self.raw_message or self.message)[:8000]
        stamp = self.event_timestamp.isoformat() if self.event_timestamp else (self.ros_time or "")
        raw = f"{self.router_id}|{stamp}|{topics}|{message}"
        canonical_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        key = self.correlation_id or f"{self.router_id}:{self.event_type}"
        return canonical_hash, key


def _active_alert(db, router_id: int, key: str):
    return db.query(Alert).filter(Alert.router_id == router_id, Alert.deduplication_key == key,
                                   Alert.is_resolved == False).first()


def _create_notification(db, event, alert, severity, notification_type, title, message, deduplication_key, available_after=None, popup_required=None, telegram_required=True):
    notification = Notification(
        event_log_id=event.id, alert_id=alert.id if alert else None, router_id=event.router_id,
        notification_type=notification_type, severity=severity, title=title[:200], message=message[:500],
        popup_required=severity != "info" if popup_required is None else popup_required,
        sound_required=severity in ("critical", "warning", "recovery") and (severity != "info" if popup_required is None else popup_required),
        telegram_required=telegram_required,
        deduplication_key=deduplication_key, available_after=available_after,
    )
    db.add(notification)
    db.flush()
    return notification


def _notification_channels(db, item, severity, force_report=False):
    """Applies channel exclusions after recovery matching, unless explicitly forced."""
    if force_report:
        return severity != "info", True
    from app.core.event_filter import is_event_excluded, load_popup_filters, load_telegram_filters
    # Critical health connectivity remains non-suppressible as documented in Filters.
    health_critical = item.topics.startswith("health,") and severity == "critical"
    popup = health_critical or not is_event_excluded(item.message, item.topics, load_popup_filters(db))
    telegram = health_critical or not is_event_excluded(item.message, item.topics, load_telegram_filters(db))
    return popup and severity != "info", telegram


def _apply_recovery_rules(db, item, event, create_notification: bool):
    """Applies configured opening/recovery pairs before generic alert handling."""
    from app.core.event_filter import event_matches_filter, load_json_setting

    now = item.received_timestamp
    rules = load_json_setting(db, "alert_recovery_rules")
    for rule in rules:
        if not rule.get("enabled", True) or not rule.get("id"):
            continue
        key = f"auto-recovery:{rule['id']}"
        if event_matches_filter(item.message, item.topics, rule.get("recovery", {})):
            alert = _active_alert(db, item.router_id, key)
            window = timedelta(seconds=max(1, int(rule.get("recovery_window_seconds", 300))))
            if alert and alert.first_seen and now - alert.first_seen <= window:
                alert.is_resolved = True
                alert.resolved_at = now
                alert.resolved_by = "automatic"
                alert.resolution_comment = rule.get("resolution_comment") or "Resuelta automáticamente al detectar recuperación."
                alert.resolution_event_id = event.id
                db.query(Notification).filter(
                    Notification.alert_id == alert.id,
                    Notification.suppressed_at.is_(None),
                    Notification.available_after.isnot(None),
                    Notification.available_after > now,
                ).update({"suppressed_at": now, "suppression_reason": "recovered_before_notification"}, synchronize_session=False)
                notification = None
                if create_notification:
                    popup_required, telegram_required = _notification_channels(db, item, "recovery", rule.get("force_recovery_report", False))
                    notification = _create_notification(
                        db, event, alert, "recovery", "auto_recovery", f"{item.router_name}: recuperación confirmada",
                        alert.resolution_comment, f"{key}:recovery:{event.id}", popup_required=popup_required, telegram_required=telegram_required,
                    )
                return alert, notification, True
            # Let generic recovery logic handle unmatched, expired, or manually
            # resolved incidents instead of swallowing the event.
            continue

        if event_matches_filter(item.message, item.topics, rule.get("opening", {})):
            alert = _active_alert(db, item.router_id, key)
            if alert:
                window = timedelta(seconds=max(1, int(rule.get("recovery_window_seconds", 300))))
                if alert.first_seen and now - alert.first_seen > window:
                    alert.is_resolved = True
                    alert.resolved_at = now
                    alert.resolved_by = "automatic"
                    alert.resolution_comment = "Incidente anterior vencido al detectar una nueva desconexión."
                    alert = None
                else:
                    alert.occurrence_count += 1
                    alert.last_seen = now
                    return alert, None, True
            severity = rule.get("severity", "warning")
            alert = Alert(
                router_id=item.router_id, alert_type=f"auto_recovery_{rule['id']}", severity=severity,
                title=f"{item.router_name}: {rule.get('name', 'evento detectado')}", message=item.message[:500],
                opening_event_id=event.id, deduplication_key=key, occurrence_count=1,
                first_seen=now, last_seen=now,
            )
            db.add(alert)
            db.flush()
            notification = None
            if create_notification:
                delay = max(0, int(rule.get("delay_seconds", 0))) if rule.get("delay_notification") else 0
                popup_required, telegram_required = _notification_channels(db, item, severity)
                notification = _create_notification(
                    db, event, alert, severity, "auto_recovery_open", alert.title, alert.message,
                    f"{key}:open:{event.id}", now + timedelta(seconds=delay) if delay else None,
                    popup_required=popup_required, telegram_required=telegram_required,
                )
            return alert, notification, True
    return None, None, False


def ingest_event(db, item: NormalizedEvent, create_alert: bool = True, create_notification: bool = True):
    """Persists one event. Duplicate deliveries update occurrence metadata only."""
    canonical_hash, deduplication_key = item.normalized()
    from app.core.event_filter import event_matches_filter, load_json_setting, load_storage_filters, is_event_excluded
    # Syslog can be lost while a router's own uplink is down. Log recovery
    # reads the same RouterOS buffer after reconnection, so it must honor the
    # same storage policy and not reinsert technical API noise.
    if item.source in ("syslog", "log_recovery") and is_event_excluded(item.message, item.topics, load_storage_filters(db)):
        return None, False, None, None
    for rule in load_json_setting(db, "event_classification_rules"):
        if rule.get("enabled", True) and event_matches_filter(item.message, item.topics, rule):
            item.event_type = rule["event_type"]
            item.severity = rule["severity"]
            canonical_hash, deduplication_key = item.normalized()
            break
    from app.api.v1.settings import get_setting
    try:
        window_minutes = max(1, int(get_setting(db, "event_consolidation_minutes", "5")))
    except ValueError:
        window_minutes = 5
    # Remote Syslog, the RouterOS memory buffer and disk recovery can deliver
    # the same incident through different sources after a reconnection.
    repeated = db.query(EventLog).filter(EventLog.router_id == item.router_id,
                                          EventLog.deduplication_key == deduplication_key,
                                          EventLog.topics == item.topics,
                                          EventLog.message == item.message,
                                          EventLog.last_seen >= item.received_timestamp - timedelta(minutes=window_minutes)).order_by(EventLog.id.desc()).first()
    if repeated:
        # A matching recovery may have resolved the alert opened by this event.
        # In that case an identical new outage is a new incident, not a duplicate.
        resolved_incident = db.query(Alert.id).filter(
            Alert.opening_event_id == repeated.id,
            Alert.is_resolved == True,
        ).first()
        if resolved_incident:
            repeated = None
    if repeated:
        repeated.last_seen = item.received_timestamp
        repeated.occurrence_count = (repeated.occurrence_count or 1) + 1
        # A duplicate delivery can be the first occurrence after an operator
        # enables a recovery rule. Evaluate it before returning early so the
        # rule can still open or resolve its alert without duplicating EventLog.
        try:
            with db.begin_nested():
                alert, notification, handled_by_recovery_rule = _apply_recovery_rules(
                    db, item, repeated, create_notification
                )
        except Exception:
            logger.exception("Recovery rule failed for consolidated event on router %s", item.router_id)
            alert, notification, handled_by_recovery_rule = None, None, False
        if handled_by_recovery_rule:
            return repeated, False, alert, notification
        active = _active_alert(db, item.router_id, deduplication_key)
        if active:
            active.last_seen = item.received_timestamp
            active.occurrence_count = (active.occurrence_count or 1) + 1
        return repeated, False, None, None
    existing = db.query(EventLog).filter(EventLog.canonical_hash == canonical_hash).first()
    if existing:
        existing.last_seen = item.received_timestamp
        return existing, False, None, None

    legacy_hash = hashlib.sha256(f"v207|{canonical_hash}".encode()).hexdigest()
    event = EventLog(router_id=item.router_id, router_name=item.router_name, ros_time=item.ros_time or "",
                     topics=item.topics, message=item.message, severity=item.severity, content_hash=legacy_hash,
                     source=item.source, event_type=item.event_type, canonical_hash=canonical_hash,
                     deduplication_key=deduplication_key, correlation_id=item.correlation_id,
                     raw_message=item.raw_message, received_timestamp=item.received_timestamp,
                     event_timestamp=item.event_timestamp, metadata_json=item.metadata)
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        event = db.query(EventLog).filter(EventLog.canonical_hash == canonical_hash).first()
        return event, False, None, None

    try:
        # Recovery configuration must never roll back the underlying Syslog event.
        with db.begin_nested():
            alert, notification, handled_by_recovery_rule = _apply_recovery_rules(db, item, event, create_notification)
    except Exception:
        logger.exception("Recovery rule failed for event %s on router %s", event.id, item.router_id)
        alert, notification, handled_by_recovery_rule = None, None, False
    if not handled_by_recovery_rule and create_alert and item.severity in ("warning", "critical"):
        alert = _active_alert(db, item.router_id, deduplication_key)
        if alert:
            alert.occurrence_count += 1
            alert.last_seen = item.received_timestamp
        else:
            alert = Alert(router_id=item.router_id, alert_type=item.event_type, severity=item.severity,
                          title=f"{item.router_name}: {item.event_type.replace('_', ' ')}",
                          message=item.message[:500], opening_event_id=event.id,
                          deduplication_key=deduplication_key, occurrence_count=1,
                          first_seen=item.received_timestamp, last_seen=item.received_timestamp)
            db.add(alert)
            db.flush()

    if not handled_by_recovery_rule and (item.event_type.endswith("_up") or item.event_type.endswith("_restored")):
        down_type = item.event_type.replace("_up", "_down").replace("_restored", "_loss")
        resolution_key = f"{item.router_id}:{down_type}"
        open_alert = _active_alert(db, item.router_id, resolution_key)
        if open_alert:
            open_alert.is_resolved = True
            open_alert.resolved_at = item.received_timestamp
            open_alert.resolution_event_id = event.id

    if not handled_by_recovery_rule and create_notification and item.severity in ("critical", "warning", "recovery"):
        popup_required, telegram_required = _notification_channels(db, item, item.severity)
        notification = _create_notification(
            db, event, alert, item.severity, item.event_type,
            f"{item.router_name}: {item.event_type.replace('_', ' ')}", item.message, deduplication_key,
            popup_required=popup_required, telegram_required=telegram_required,
        )
    return event, True, alert, notification
