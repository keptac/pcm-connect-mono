from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..db import get_session
from ..models import Student, User, Department
from ..deps import get_current_user
from ..services.students import mark_alumni

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/students")
def student_analytics(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    mark_alumni(session)
    query = select(Student)
    if current.role != "admin" and current.university_id:
        query = query.where(Student.university_id == current.university_id)
    students = session.exec(query).all()

    status_counts = defaultdict(int)
    program_counts = defaultdict(int)
    gender_counts = defaultdict(int)
    department_counts = defaultdict(int)
    dept_lookup = {d.id: d.name for d in session.exec(select(Department)).all()}

    for student in students:
        status_counts[student.status] += 1
        if student.program:
            program_counts[student.program] += 1
        if student.gender:
            gender_counts[student.gender] += 1
        if student.department_id:
            department_counts[dept_lookup.get(student.department_id, str(student.department_id))] += 1

    return {
        "total": len(students),
        "by_status": dict(status_counts),
        "by_program": dict(program_counts),
        "by_gender": dict(gender_counts),
        "by_department": dict(department_counts),
    }
