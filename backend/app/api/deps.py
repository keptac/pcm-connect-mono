from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from ..core.config import settings
from ..db.session import get_db
from ..models import User
from ..services.rbac import get_user_roles
from ..services.user_lifecycle import ensure_user_lifecycle_state

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN_ROLES = ["super_admin"]
CHAPTER_ROLES = ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
PROGRAM_ROLES = ["super_admin", "student_admin", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
FUNDING_ROLES = ["super_admin", "student_admin", "alumni_admin", "finance_officer", "students_finance", "executive", "director"]
FUNDING_WRITE_ROLES = ["super_admin", "finance_officer", "students_finance", "executive"]
GENERAL_NETWORK_ROLES = [*CHAPTER_ROLES, "general_user"]
GENERAL_USER_ROLES = ["general_user"]
GLOBAL_VISIBILITY_ROLES = ["super_admin", "executive", "director"]


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        email = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).filter(User.email == email).first()
    user = ensure_user_lifecycle_state(db, user) if user else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_role(required_roles: list[str]):
    def _guard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        user_roles = get_user_roles(db, user)
        if not set(required_roles).intersection(set(user_roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _guard


def require_non_service_recovery(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
    user_roles = get_user_roles(db, user)
    if "service_recovery" in user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return user


def get_scope(user: User):
    return user.university_id


def resolve_university_scope(user: User, requested_university_id: int | None = None) -> int | None:
    if user.university_id:
        if requested_university_id and requested_university_id != user.university_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
        return user.university_id
    return requested_university_id


def affiliated_university_id(user: User) -> int | None:
    return user.university_id or (user.member.university_id if user.member else None)


def is_student_profile(user: User) -> bool:
    return bool(user.member and (user.member.status or "Student") == "Student")


def require_marketplace_access(user: User = Depends(get_current_user), db: Session | None = Depends(get_db)) -> User:
    if isinstance(db, Session) and "service_recovery" in get_user_roles(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    if is_student_profile(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marketplace is only available to non-student profiles")
    return user
