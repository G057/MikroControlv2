from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class RouterGroup(Base):
    __tablename__ = "router_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    routers = relationship("Router", back_populates="group")


class RouterTag(Base):
    __tablename__ = "router_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(7), default="#10B981")


class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    hostname = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=False)
    mac_address = Column(String(17), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(50), nullable=True)
    routeros_version = Column(String(20), nullable=True)
    identity = Column(String(100), nullable=True)

    access_method = Column(String(20), default="ip_public")
    access_port = Column(Integer, default=8728)
    use_ssl = Column(Boolean, default=False)

    api_username = Column(String(50), default="admin")
    api_password_encrypted = Column(String(200), nullable=True)

    wg_address = Column(String(18), nullable=True)
    wg_endpoint = Column(String(200), nullable=True)
    wg_public_key = Column(String(100), nullable=True)

    group_id = Column(Integer, ForeignKey("router_groups.id"), nullable=True)

    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_check = Column(DateTime(timezone=True), nullable=True)

    cpu_usage = Column(Float, nullable=True)
    ram_usage = Column(Float, nullable=True)
    ram_total = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    voltage = Column(Float, nullable=True)
    uptime = Column(String(50), nullable=True)
    hdd_free = Column(Float, nullable=True)
    hdd_total = Column(Float, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)

    client_name = Column(String(100), nullable=True)
    client_phone = Column(String(20), nullable=True)
    client_email = Column(String(100), nullable=True)

    notes = Column(Text, nullable=True)
    tag_ids = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    group = relationship("RouterGroup", back_populates="routers")
    backups = relationship("Backup", back_populates="router")
    alerts = relationship("Alert", back_populates="router")
