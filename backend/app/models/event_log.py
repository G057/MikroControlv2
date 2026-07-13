from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, Index
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
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    router = relationship("Router")

    __table_args__ = (
        Index("ix_event_logs_router_time", "router_id", "ros_time"),
    )
