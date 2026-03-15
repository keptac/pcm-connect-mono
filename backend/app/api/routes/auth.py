from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.security import create_access_token, create_refresh_token, hash_password, verify_password
from ...db.session import get_db
from ...models import Member, Role, User, UserRole
from ...services.user_lifecycle import deletion_due_on, ensure_user_lifecycle_state, has_tenure_exemption, tenure_months_for
from ...schemas import (
    AuthSession,
    ChangePasswordRequest,
    GeneralUserLookupRequest,
    GeneralUserMatchRead,
    GeneralUserRegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserRead,
)
from ...services.rbac import get_user_roles
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _serialize_user(db: Session, user: User) -> UserRead:
    roles = get_user_roles(db, user)
    tenure_exempt = has_tenure_exemption(roles)
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        university_id=user.university_id,
        university_name=user.university.name if user.university else None,
        member_id=str(user.member.id) if user.member else None,
        member_number=user.member.member_id if user.member else None,
        member_status=user.member.status if user.member else None,
        member_university_id=user.member.university_id if user.member else None,
        member_university_name=user.member.university.name if user.member and user.member.university else None,
        donor_interest=bool(user.donor_interest),
        is_active=user.is_active,
        is_system_admin=bool(user.is_system_admin),
        subject_to_tenure=bool(user.subject_to_tenure) and not tenure_exempt,
        force_password_reset=bool(user.force_password_reset),
        tenure_months=None if tenure_exempt else tenure_months_for(user),
        tenure_starts_on=None if tenure_exempt else user.tenure_starts_on,
        tenure_ends_on=None if tenure_exempt else user.tenure_ends_on,
        disabled_at=user.disabled_at,
        deletion_due_at=deletion_due_on(user, tenure_exempt=tenure_exempt),
        roles=roles,
    )


def _mask_email(email: str | None) -> str | None:
    normalized = (email or "").strip()
    if not normalized or "@" not in normalized:
        return None

    local_part, domain = normalized.split("@", 1)
    visible_prefix = local_part[:2]
    masked_local = f"{visible_prefix}{'*' * max(1, len(local_part) - len(visible_prefix))}"
    return f"{masked_local}@{domain}"


def _preferred_sign_in_identifier(user: User) -> str:
    return user.email


def _normalize_registration_email(email: str | None) -> str:
    normalized = (email or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address")
    local_part, _, domain = normalized.partition("@")
    if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address")
    return normalized


def _ensure_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role:
        return role

    role = Role(name=role_name)
    db.add(role)
    db.flush()
    return role


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.email.strip().lower()
    user = (
        db.query(User)
        .outerjoin(Member, Member.id == User.member_id)
        .filter(
            or_(
                func.lower(User.email) == identifier,
                func.lower(Member.member_id) == identifier,
            )
        )
        .first()
    )
    user = ensure_user_lifecycle_state(db, user) if user else None
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled")
    return TokenPair(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
        password_reset_required=bool(user.force_password_reset),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.refresh_token, settings.secret_key, algorithms=["HS256"])
        if data.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        subject = data.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).filter(User.email == subject).first()
    user = ensure_user_lifecycle_state(db, user) if user else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        password_reset_required=bool(user.force_password_reset),
    )


@router.post("/general-registration/search", response_model=list[GeneralUserMatchRead])
def search_general_registration_matches(
    payload: GeneralUserLookupRequest,
    db: Session = Depends(get_db),
):
    exact_last_name = payload.last_name.strip()
    if not exact_last_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Last name is required")

    matches = (
        db.query(Member)
        .outerjoin(User, User.member_id == Member.id)
        .filter(
            Member.active.is_(True),
            Member.university_id == payload.university_id,
            Member.start_year == payload.start_year,
            Member.last_name == exact_last_name,
            func.lower(Member.status) != "student",
            User.id.is_(None),
        )
        .order_by(Member.first_name.asc(), Member.last_name.asc())
        .all()
    )

    return [
        GeneralUserMatchRead(
            member_id=str(member.id),
            member_number=member.member_id,
            first_name=member.first_name,
            last_name=member.last_name,
            university_id=member.university_id,
            university_name=member.university.name if member.university else None,
            start_year=member.start_year,
            status=member.status or "Student",
            program_of_study_name=member.program_of_study.name if member.program_of_study else None,
            email_hint=_mask_email(member.email),
        )
        for member in matches
    ]


@router.post("/general-registration/register", response_model=AuthSession)
def register_general_user(
    payload: GeneralUserRegisterRequest,
    db: Session = Depends(get_db),
):
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")
    registration_email = _normalize_registration_email(payload.email)

    try:
        member_uuid = UUID(payload.member_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid member record") from exc

    member = db.query(Member).filter(Member.id == member_uuid).first()
    if not member or not member.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching member record not found")
    if (member.status or "Student") == "Student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student profiles cannot self-register here")
    if db.query(User).filter(User.member_id == member.id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account already exists for this record")
    if db.query(User).filter(func.lower(User.email) == registration_email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That email is already in use")

    new_user = User(
        email=registration_email,
        name=" ".join(part for part in [member.first_name, member.last_name] if part).strip() or member.email,
        password_hash=hash_password(payload.password),
        university_id=None,
        member_id=member.id,
        donor_interest=payload.donor_interest,
        subject_to_tenure=False,
        force_password_reset=False,
    )
    db.add(new_user)
    db.flush()
    member.email = registration_email

    general_role = _ensure_role(db, "general_user")
    db.add(UserRole(user_id=new_user.id, role_id=general_role.id))
    db.commit()
    db.refresh(new_user)

    return AuthSession(
        access_token=create_access_token(new_user.email),
        refresh_token=create_refresh_token(new_user.email),
        user=_serialize_user(db, new_user),
        sign_in_identifier=_preferred_sign_in_identifier(new_user),
    )


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize_user(db, user)


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(payload.new_password)
    user.force_password_reset = False
    db.commit()
    db.refresh(user)
    return _serialize_user(db, user)
