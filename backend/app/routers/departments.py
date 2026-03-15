from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Department, User
from ..schemas import DepartmentCreate, DepartmentRead
from ..deps import require_role, get_current_user

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if current.role == "admin":
        return session.exec(select(Department)).all()
    if current.university_id:
        return session.exec(select(Department).where(Department.university_id == current.university_id)).all()
    return []


@router.post("", response_model=DepartmentRead)
def create_department(
    payload: DepartmentCreate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin")),
):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient role")
    dept = Department(**payload.dict())
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return dept
