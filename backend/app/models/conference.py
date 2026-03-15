from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from ..db.base import Base


class Conference(Base):
    __tablename__ = "conferences"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    union_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    universities = relationship("University", back_populates="conference")
