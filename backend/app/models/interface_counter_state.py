from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class InterfaceCounterState(Base):
    """Último contador crudo (rx-byte/tx-byte) por interfaz.

    Persiste el baseline que el sampler usa para calcular el delta entre
    muestras. Sobrevive a reinicios del proceso, evitando perder una muestra
    cada vez que se reinicia uvicorn.
    """
    __tablename__ = "interface_counter_state"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    interface = Column(String(100), nullable=False)
    rx_byte = Column(BigInteger, nullable=False, default=0)
    tx_byte = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    router = relationship("Router")

    __table_args__ = (
        UniqueConstraint("router_id", "interface", name="uq_interface_counter_state"),
    )
