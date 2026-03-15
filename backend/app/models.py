from datetime import date, datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class University(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    country: Optional[str] = None
    city: Optional[str] = None


class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    university_id: int = Field(foreign_key="university.id")


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(index=True)  # admin | student_admin | leader
    university_id: Optional[int] = Field(default=None, foreign_key="university.id")
    is_active: bool = True


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: Optional[str] = Field(default=None, index=True)
    first_name: str
    last_name: str
    email: Optional[str] = Field(default=None, index=True)
    gender: Optional[str] = None
    program: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"  # active | alumni
    university_id: int = Field(foreign_key="university.id")
    department_id: Optional[int] = Field(default=None, foreign_key="department.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReportUpload(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    university_id: int = Field(foreign_key="university.id")
    uploaded_by: int = Field(foreign_key="user.id")
    original_filename: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    report_period: Optional[str] = None


class ReportRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="reportupload.id")
    metric: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    row_data: Optional[str] = None  # JSON string of original row
