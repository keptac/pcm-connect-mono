from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from ..db.base import Base


class University(Base):
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    short_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    region = Column(String, nullable=True)
    conference_id = Column(Integer, ForeignKey("conferences.id"), nullable=True)
    mission_focus = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conference = relationship("Conference", back_populates="universities")
    programs = relationship("Program", back_populates="university", cascade="all, delete-orphan")
    academic_programs = relationship("AcademicProgram", back_populates="university", cascade="all, delete-orphan")
    members = relationship("Member", back_populates="university")
    users = relationship("User", back_populates="university")
    funding_records = relationship("FundingRecord", back_populates="university", cascade="all, delete-orphan")
    program_updates = relationship("ProgramUpdate", back_populates="university", cascade="all, delete-orphan")
    events = relationship("CampusEvent", back_populates="university", cascade="all, delete-orphan")
    broadcasts = relationship("ProgramBroadcast", back_populates="university", cascade="all, delete-orphan")
    marketplace_listings = relationship("MarketplaceListing", back_populates="university", cascade="all, delete-orphan")
