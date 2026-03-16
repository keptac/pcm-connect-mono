from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models import Department
from ...schemas import DepartmentCreate, DepartmentRead
from ..deps import require_role

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(db: Session = Depends(get_db), user=Depends(require_role(["super_admin", "student_admin", "secretary"]))):
    return db.query(Department).all()


@router.post("", response_model=DepartmentRead)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db), user=Depends(require_role(["super_admin", "student_admin", "secretary"]))):
    dept = Department(**payload.dict())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept
