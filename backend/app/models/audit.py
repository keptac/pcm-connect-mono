from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from ..db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    meta_json = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
