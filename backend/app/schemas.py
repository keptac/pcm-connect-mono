from datetime import date
from typing import Optional, List
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class UniversityCreate(BaseModel):
    name: str
    country: Optional[str] = None
    city: Optional[str] = None


class UniversityRead(UniversityCreate):
    id: int


class DepartmentCreate(BaseModel):
    name: str
    university_id: int


class DepartmentRead(DepartmentCreate):
    id: int


class UserCreate(BaseModel):
    email: str
    password: str
    role: str
    university_id: Optional[int] = None


class UserRead(BaseModel):
    id: int
    email: str
    role: str
    university_id: Optional[int] = None
    is_active: bool


class StudentCreate(BaseModel):
    student_id: Optional[str] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    gender: Optional[str] = None
    program: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    university_id: int
    department_id: Optional[int] = None


class StudentRead(StudentCreate):
    id: int
    status: str


class StudentUpdate(BaseModel):
    student_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    program: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    department_id: Optional[int] = None


class ReportUploadRead(BaseModel):
    id: int
    university_id: int
    uploaded_by: int
    original_filename: str
    report_period: Optional[str] = None


class ReportRowRead(BaseModel):
    id: int
    metric: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class ReportAnalysis(BaseModel):
    total_rows: int
    metrics: List[str]
    totals_by_metric: dict
    categories: dict
