from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class RouterConnectivityState(Base):
    __tablename__ = "router_connectivity_states"

    router_id = Column(Integer, ForeignKey("routers.id"), primary_key=True)
    current_state = Column(String(24), nullable=False, default="UNKNOWN")
    consecutive_failures = Column(Integer, nullable=False, default=0)
    consecutive_successes = Column(Integer, nullable=False, default=0)
    offline_since = Column(DateTime(timezone=True), nullable=True)
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_state_change_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    event_log_id = Column(Integer, ForeignKey("event_logs.id"), nullable=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=True, index=True)
    notification_type = Column(String(64), nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    popup_required = Column(Boolean, nullable=False, default=False)
    sound_required = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    deduplication_key = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_notifications_cursor", "id", "status"),
    )


class UnmatchedSyslogMessage(Base):
    __tablename__ = "unmatched_syslog_messages"

    id = Column(Integer, primary_key=True, index=True)
    source_ip = Column(String(45), nullable=True, index=True)
    parsed_hostname = Column(String(200), nullable=True, index=True)
    raw_message = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reason = Column(String(100), nullable=False)
    candidate_router_ids = Column(JSON, nullable=False, default=list)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False, index=True)
    channel = Column(String(30), nullable=False)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, nullable=False, default=False)
    error = Column(Text, nullable=True)
    response_code = Column(Integer, nullable=True)

    __table_args__ = (Index("ix_notification_delivery_once", "notification_id", "channel", unique=True),)


class SyslogMetric(Base):
    __tablename__ = "syslog_metrics"

    key = Column(String(80), primary_key=True)
    value = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
