from sqlalchemy import Column, Integer, String, ForeignKey, Float, Date, DateTime, Text
from sqlalchemy.orm import relationship
from ..db.base import Base


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, default="active")
    description = Column(Text, nullable=True)
    audience = Column(String, nullable=True)
    manager_name = Column(String, nullable=True)
    target_beneficiaries = Column(Integer, nullable=True)
    beneficiaries_served = Column(Integer, default=0)
    annual_budget = Column(Float, nullable=True)
    duration_weeks = Column(Float, nullable=True)
    level = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    last_update_at = Column(DateTime, nullable=True)

    university = relationship("University", back_populates="programs")
    members = relationship("Member", back_populates="program")
    funding_records = relationship("FundingRecord", back_populates="program")
    updates = relationship("ProgramUpdate", back_populates="program", cascade="all, delete-orphan")
    events = relationship("CampusEvent", back_populates="program", cascade="all, delete-orphan")
    broadcasts = relationship("ProgramBroadcast", back_populates="program", cascade="all, delete-orphan")
