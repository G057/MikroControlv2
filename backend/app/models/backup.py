from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Backup(Base):
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    backup_type = Column(String(20), nullable=False)  # binary, export, auto
    filename = Column(String(200), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String(500), nullable=False)
    routeros_version = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    is_restored = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    router = relationship("Router", back_populates="backups")
