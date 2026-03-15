from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import User
from ..schemas import UserCreate, UserRead
from ..services.auth import hash_password
from ..deps import require_role

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(
    current: User = Depends(require_role("admin", "student_admin", "leader")),
):
    return current


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin")),
):
    return session.exec(select(User)).all()


@router.post("", response_model=UserRead)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin")),
):
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        university_id=payload.university_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
