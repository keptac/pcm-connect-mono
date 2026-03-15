from datetime import date
from sqlmodel import Session, select
from ..models import Student


def mark_alumni(session: Session) -> int:
    today = date.today()
    students = session.exec(select(Student).where(Student.end_date.is_not(None))).all()
    updated = 0
    for student in students:
        if student.end_date and student.end_date < today and student.status != "alumni":
            student.status = "alumni"
            updated += 1
    if updated:
        session.commit()
    return updated
