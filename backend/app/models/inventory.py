from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    item_type = Column(String(30), nullable=False)  # router, switch, ap, camera, olt, ont, ups, server
    name = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    mac_address = Column(String(17), nullable=True)
    ip_address = Column(String(45), nullable=True)
    location = Column(String(200), nullable=True)
    client_name = Column(String(100), nullable=True)
    status = Column(String(20), default="active")  # active, inactive, maintenance
    purchase_date = Column(DateTime(timezone=True), nullable=True)
    warranty_until = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
