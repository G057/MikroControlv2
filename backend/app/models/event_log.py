from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    router_name = Column(String(100), nullable=False)
    ros_time = Column(String(30), nullable=False)
    topics = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, unique=True)
    source = Column(String(30), nullable=False, default="legacy", index=True)
    event_type = Column(String(80), nullable=False, default="unclassified", index=True)
    canonical_hash = Column(String(64), nullable=True, unique=True, index=True)
    deduplication_key = Column(String(255), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    raw_message = Column(Text, nullable=True)
    received_timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    router = relationship("Router")

    __table_args__ = (
        Index("ix_event_logs_router_time", "router_id", "ros_time"),
        # Filtro por router + orden por id (la query ordena por id desc).
        Index("ix_event_logs_router_id_id", "router_id", "id"),
        # Filtro por severidad + orden por id.
        Index("ix_event_logs_severity_id", "severity", "id"),
        # Filtro por severidad + router + orden por id (counts).
        Index("ix_event_logs_severity_router_id", "severity", "router_id", "id"),
    )
