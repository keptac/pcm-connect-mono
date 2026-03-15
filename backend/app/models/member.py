from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from ..db.base import Base


class Member(Base):
    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    program_of_study_id = Column(Integer, ForeignKey("academic_programs.id"), nullable=True)
    member_id = Column(String, unique=True, index=True, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    gender = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    start_year = Column(Integer, nullable=True)
    expected_graduation_date = Column(Date, nullable=True)
    intake = Column(String, nullable=True)
    status = Column(String, default="Student")
    employment_status = Column(String, nullable=True)
    employer_name = Column(String, nullable=True)
    current_city = Column(String, nullable=True)
    services_offered = Column(Text, nullable=True)
    products_supplied = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    university = relationship("University", back_populates="members")
    program = relationship("Program", back_populates="members")
    program_of_study = relationship("AcademicProgram", back_populates="members")
    history = relationship("MembershipStatusHistory", back_populates="member", cascade="all, delete-orphan")
    user = relationship("User", back_populates="member", uselist=False)


class MembershipStatusHistory(Base):
    __tablename__ = "membership_status_history"

    id = Column(Integer, primary_key=True)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(String, nullable=True)

    member = relationship("Member", back_populates="history")
