from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class InterfaceTraffic(Base):
    """Muestra periódica de tráfico por interfaz (bits por segundo).

    El sampler calcula rx_bps/tx_bps a partir del delta de los contadores
    rx-byte/tx-byte entre dos muestras consecutivas.
    """
    __tablename__ = "interface_traffic"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    interface = Column(String(100), nullable=False)
    rx_bps = Column(Float, nullable=False, default=0)
    tx_bps = Column(Float, nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    router = relationship("Router")

    __table_args__ = (
        Index("ix_interface_traffic_lookup", "router_id", "interface", "timestamp"),
    )
