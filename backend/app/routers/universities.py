from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..db import get_session
from ..models import University, User
from ..schemas import UniversityCreate, UniversityRead
from ..deps import require_role, get_current_user

router = APIRouter(prefix="/universities", tags=["universities"])


@router.get("", response_model=list[UniversityRead])
def list_universities(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if current.role == "admin":
        return session.exec(select(University)).all()
    if current.university_id:
        uni = session.get(University, current.university_id)
        return [uni] if uni else []
    return []


@router.post("", response_model=UniversityRead)
def create_university(
    payload: UniversityCreate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin")),
):
    uni = University(**payload.dict())
    session.add(uni)
    session.commit()
    session.refresh(uni)
    return uni
