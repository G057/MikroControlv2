from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class RouterHistory(Base):
    __tablename__ = "router_history"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    router_name = Column(String(100), nullable=False)
    ros_id = Column(String(20), nullable=False)
    action = Column(String(200), nullable=False)
    redo = Column(Text, nullable=False)
    undo = Column(Text, nullable=True)
    by_user = Column(String(50), nullable=True)
    policy = Column(String(100), nullable=True)
    ros_time = Column(String(30), nullable=False)
    trace = Column(String(200), nullable=True)
    undoable = Column(String(10), nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())

    router = relationship("Router")

    __table_args__ = (
        UniqueConstraint("router_id", "ros_id", name="uq_router_history_ros_id"),
        Index("ix_router_history_router_time", "router_id", "ros_time"),
        # Filtro por router + rango de fecha (first_seen) en la vista de historial.
        Index("ix_router_history_router_first_seen", "router_id", "first_seen"),
    )
