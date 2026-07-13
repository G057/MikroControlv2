from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    alert_type = Column(String(30), nullable=False)  # interface_down, high_cpu, low_disk, backup_failed, high_temp
    threshold = Column(Float, nullable=True)
    severity = Column(String(20), default="warning")  # info, warning, critical
    notify_telegram = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=True)
    alert_type = Column(String(30), nullable=False)
    severity = Column(String(20), default="warning")
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(50), nullable=True)
    resolution_comment = Column(Text, nullable=True)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    router = relationship("Router", back_populates="alerts")
    rule = relationship("AlertRule")

    __table_args__ = (
        # Filtros frecuentes en /events y paneles: por router, por estado y por severidad.
        Index("ix_alerts_router_created", "router_id", "created_at"),
        Index("ix_alerts_resolved_created", "is_resolved", "created_at"),
        Index("ix_alerts_severity_created", "severity", "created_at"),
    )
