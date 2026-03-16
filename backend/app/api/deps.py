from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import false, or_
from sqlalchemy.orm import Session
from ..core.config import settings
from ..db.session import get_db
from ..models import Conference, Union, University, User
from ..services.rbac import get_user_roles
from ..services.user_lifecycle import ensure_user_lifecycle_state

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN_ROLES = ["super_admin"]
CHAPTER_ROLES = ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
PROGRAM_ROLES = ["super_admin", "student_admin", "secretary", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
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
    return user.university_id or user.conference_id or user.union_id


def _university_scope_row(db: Session, university_id: int) -> tuple[int | None, int | None]:
    record = (
        db.query(University.conference_id, Conference.union_id)
        .outerjoin(Conference, University.conference_id == Conference.id)
        .filter(University.id == university_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found")
    return record[0], record[1]


def _university_conference_id(db: Session, university_id: int) -> int | None:
    conference_id, _ = _university_scope_row(db, university_id)
    return conference_id


def _university_union_id(db: Session, university_id: int) -> int | None:
    _, union_id = _university_scope_row(db, university_id)
    return union_id


def _conference_union_id(db: Session, conference_id: int) -> int | None:
    record = (
        db.query(Conference.union_id)
        .filter(Conference.id == conference_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")
    return record[0]


def resolve_university_scope(db: Session, user: User, requested_university_id: int | None = None) -> int | None:
    if user.university_id:
        if requested_university_id and requested_university_id != user.university_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
        return user.university_id
    if user.conference_id:
        if requested_university_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Select a university within your assigned conference")
        if _university_conference_id(db, requested_university_id) != user.conference_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
        return requested_university_id
    if user.union_id:
        if requested_university_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Select a university within your assigned union")
        if _university_union_id(db, requested_university_id) != user.union_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
        return requested_university_id
    return requested_university_id


def resolve_requested_scope(
    db: Session,
    user: User,
    requested_university_id: int | None = None,
    requested_conference_id: int | None = None,
    requested_union_id: int | None = None,
) -> tuple[int | None, int | None, int | None]:
    selected_scope_count = sum(
        value is not None
        for value in [requested_university_id, requested_conference_id, requested_union_id]
    )
    if selected_scope_count > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select only one scope")

    if user.university_id:
        if requested_conference_id is not None or requested_union_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid scope")
        if requested_university_id and requested_university_id != user.university_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
        return user.university_id, None, None

    if user.conference_id:
        if requested_union_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid union scope")
        if requested_conference_id and requested_conference_id != user.conference_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid conference scope")
        if requested_university_id:
            if _university_conference_id(db, requested_university_id) != user.conference_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
            return requested_university_id, None, None
        return None, user.conference_id, None

    if user.union_id:
        if requested_union_id and requested_union_id != user.union_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid union scope")
        if requested_conference_id:
            if _conference_union_id(db, requested_conference_id) != user.union_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid conference scope")
            return None, requested_conference_id, None
        if requested_university_id:
            if _university_union_id(db, requested_university_id) != user.union_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid university scope")
            return requested_university_id, None, None
        return None, None, user.union_id

    return requested_university_id, requested_conference_id, requested_union_id


def resolve_visible_university_ids(
    db: Session,
    user: User,
    requested_university_id: int | None = None,
    requested_conference_id: int | None = None,
    requested_union_id: int | None = None,
) -> set[int] | None:
    scoped_university_id, scoped_conference_id, scoped_union_id = resolve_requested_scope(
        db,
        user,
        requested_university_id=requested_university_id,
        requested_conference_id=requested_conference_id,
        requested_union_id=requested_union_id,
    )
    if scoped_university_id:
        return {scoped_university_id}
    if scoped_conference_id:
        conference = db.query(Conference).filter(Conference.id == scoped_conference_id).first()
        if not conference:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")
        return {
            item[0]
            for item in (
                db.query(University.id)
                .filter(University.conference_id == scoped_conference_id)
                .all()
            )
        }
    if not scoped_union_id:
        return None

    union = db.query(Union).filter(Union.id == scoped_union_id).first()
    if not union:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Union not found")

    return {
        item[0]
        for item in (
            db.query(University.id)
            .join(Conference, University.conference_id == Conference.id)
            .filter(Conference.union_id == scoped_union_id)
            .all()
        )
    }


def apply_university_scope_filter(query, model, university_ids: set[int] | None, include_network_records: bool = False):
    if university_ids is None:
        return query
    if not university_ids:
        return query.filter(model.university_id.is_(None)) if include_network_records else query.filter(false())

    condition = model.university_id.in_(sorted(university_ids))
    if include_network_records:
        condition = or_(condition, model.university_id.is_(None))
    return query.filter(condition)


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
