"""Single, idempotent write path for router events and notifications."""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models.alert import Alert
from app.models.event_log import EventLog
from app.models.monitoring import Notification


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


def ingest_event(db, item: NormalizedEvent, create_alert: bool = True, create_notification: bool = True):
    """Persists one event. Duplicate deliveries update occurrence metadata only."""
    canonical_hash, deduplication_key = item.normalized()
    from app.core.event_filter import event_matches_filter, load_json_setting
    for rule in load_json_setting(db, "event_classification_rules"):
        if rule.get("enabled", True) and event_matches_filter(item.message, item.topics, rule):
            item.event_type = rule["event_type"]
            item.severity = rule["severity"]
            canonical_hash, deduplication_key = item.normalized()
            break
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

    alert = None
    if create_alert and item.severity in ("warning", "critical"):
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

    if item.event_type.endswith("_up") or item.event_type.endswith("_restored"):
        down_type = item.event_type.replace("_up", "_down").replace("_restored", "_loss")
        resolution_key = f"{item.router_id}:{down_type}"
        open_alert = _active_alert(db, item.router_id, resolution_key)
        if open_alert:
            open_alert.is_resolved = True
            open_alert.resolved_at = item.received_timestamp
            open_alert.resolution_event_id = event.id

    notification = None
    if create_notification and item.severity in ("critical", "warning", "recovery"):
        notification = Notification(event_log_id=event.id, alert_id=alert.id if alert else None,
                                    router_id=item.router_id, notification_type=item.event_type,
                                    severity=item.severity, title=f"{item.router_name}: {item.event_type.replace('_', ' ')}",
                                    message=item.message[:500], popup_required=item.severity != "info",
                                    sound_required=item.severity in ("critical", "warning", "recovery"),
                                    deduplication_key=deduplication_key)
        db.add(notification)
        db.flush()
    return event, True, alert, notification
