from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class ConfigTemplate(Base):
    __tablename__ = "config_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # firewall, nat, vlan, dhcp, pppoe, wireguard, hotspot, custom
    template_content = Column(Text, nullable=False)
    variables = Column(Text, nullable=True)  # JSON: {"var1": "default_value", ...}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
