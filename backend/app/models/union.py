from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from ..db.base import Base


class Union(Base):
    __tablename__ = "unions"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conferences = relationship("Conference", back_populates="union")
    users = relationship("User", back_populates="union")
