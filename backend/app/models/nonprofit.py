from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.base import Base


class ReportingPeriod(Base):
    __tablename__ = "reporting_periods"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    label = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FundingRecord(Base):
    __tablename__ = "funding_records"

    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    source_name = Column(String, nullable=False)
    entry_type = Column(String, default="donation")
    flow_direction = Column(String, default="inflow")
    receipt_category = Column(String, nullable=True)
    category_detail = Column(String, nullable=True)
    reporting_window = Column(String, default="monthly")
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    transaction_date = Column(Date, nullable=False)
    channel = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    university = relationship("University", back_populates="funding_records")
    program = relationship("Program", back_populates="funding_records")


class ProgramUpdate(Base):
    __tablename__ = "program_updates"

    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    title = Column(String, nullable=False)
    event_name = Column(String, nullable=True)
    event_detail = Column(String, nullable=True)
    reporting_period = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    outcomes = Column(Text, nullable=True)
    challenges = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)
    beneficiaries_reached = Column(Integer, default=0)
    volunteers_involved = Column(Integer, default=0)
    funds_used = Column(Float, nullable=True)
    attachments_json = Column(Text, nullable=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    university = relationship("University", back_populates="program_updates")
    program = relationship("Program", back_populates="updates")


class MandatoryProgram(Base):
    __tablename__ = "mandatory_programs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    program_type = Column(String, default="event")
    allow_other_detail = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CampusEvent(Base):
    __tablename__ = "campus_events"

    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    title = Column(String, nullable=False)
    event_type = Column(String, nullable=True)
    audience = Column(String, nullable=True)
    status = Column(String, default="scheduled")
    venue = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    organizer_name = Column(String, nullable=True)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    university = relationship("University", back_populates="events")
    program = relationship("Program", back_populates="events")
