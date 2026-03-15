import csv
from datetime import datetime, date
from io import StringIO
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Student, User
from ..schemas import StudentCreate, StudentRead, StudentUpdate
from ..deps import get_current_user, require_role
from ..services.students import mark_alumni

router = APIRouter(prefix="/students", tags=["students"])


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("", response_model=list[StudentRead])
def list_students(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    mark_alumni(session)
    if current.role == "admin":
        return session.exec(select(Student)).all()
    if current.university_id:
        return session.exec(select(Student).where(Student.university_id == current.university_id)).all()
    return []


@router.post("", response_model=StudentRead)
def create_student(
    payload: StudentCreate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin", "student_admin")),
):
    if current.role != "admin" and payload.university_id != current.university_id:
        raise HTTPException(status_code=403, detail="Invalid university access")
    student = Student(**payload.dict())
    if student.end_date and student.end_date < date.today():
        student.status = "alumni"
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin", "student_admin")),
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current.role != "admin" and student.university_id != current.university_id:
        raise HTTPException(status_code=403, detail="Invalid university access")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(student, key, value)
    student.updated_at = datetime.utcnow()
    if student.end_date and student.end_date < date.today():
        student.status = "alumni"
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@router.post("/import", response_model=dict)
def import_students(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin", "student_admin")),
):
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    created = 0
    updated = 0
    for row in reader:
        uni_id = row.get("university_id")
        if current.role != "admin":
            uni_id = str(current.university_id) if current.university_id else None
        if not uni_id:
            continue
        existing = None
        if row.get("email"):
            existing = session.exec(select(Student).where(Student.email == row.get("email"))).first()
        if not existing and row.get("student_id"):
            existing = session.exec(select(Student).where(Student.student_id == row.get("student_id"))).first()
        data = {
            "student_id": row.get("student_id"),
            "first_name": row.get("first_name") or "",
            "last_name": row.get("last_name") or "",
            "email": row.get("email"),
            "gender": row.get("gender"),
            "program": row.get("program"),
            "start_date": parse_date(row.get("start_date")),
            "end_date": parse_date(row.get("end_date")),
            "university_id": int(uni_id),
            "department_id": int(row.get("department_id")) if row.get("department_id") else None,
        }
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            if existing.end_date and existing.end_date < date.today():
                existing.status = "alumni"
            session.add(existing)
            updated += 1
        else:
            student = Student(**data)
            if student.end_date and student.end_date < date.today():
                student.status = "alumni"
            session.add(student)
            created += 1
    session.commit()
    return {"created": created, "updated": updated}


@router.post("/reconcile", response_model=dict)
def reconcile_students(
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin", "student_admin")),
):
    updated = mark_alumni(session)
    return {"updated": updated}
