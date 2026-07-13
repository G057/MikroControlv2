from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    widgets = Column(Text, nullable=False, default="[]")

    user = relationship("User")
