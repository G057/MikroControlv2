from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(200), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        # Orden/paginado por fecha (siempre presente) y rangos date_from/date_to.
        Index("ix_audit_logs_timestamp", "timestamp"),
        # Filtros comunes + orden por fecha (evita el sort en tablas grandes).
        Index("ix_audit_logs_resource_type_timestamp", "resource_type", "timestamp"),
        Index("ix_audit_logs_username_timestamp", "username", "timestamp"),
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
    )
