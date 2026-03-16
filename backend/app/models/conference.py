from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.base import Base


class Conference(Base):
    __tablename__ = "conferences"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    union_name = Column(String, nullable=False)
    union_id = Column(Integer, ForeignKey("unions.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    union = relationship("Union", back_populates="conferences")
    universities = relationship("University", back_populates="conference")
