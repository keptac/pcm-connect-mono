from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    donor_interest = Column(Boolean, default=False, nullable=False)
    chat_public_key = Column(Text, nullable=True)
    chat_private_key_encrypted = Column(Text, nullable=True)
    chat_key_salt = Column(String, nullable=True)
    chat_key_iv = Column(String, nullable=True)
    chat_key_algorithm = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    university = relationship("University", back_populates="users")
    member = relationship("Member", back_populates="user")
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    marketplace_interests = relationship("MarketplaceInterest", back_populates="user", cascade="all, delete-orphan")
