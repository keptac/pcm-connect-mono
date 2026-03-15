from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models import Member, Role, User, UserRole
from ...schemas import UserCreate, UserPasswordRecovery, UserRead, UserUpdate
from ...core.security import hash_password
from ...services.rbac import get_user_roles, normalize_role_name
from ...services.user_lifecycle import (
    DEFAULT_TENURE_MONTHS,
    deletion_due_on,
    has_tenure_exemption,
    resolve_tenure_window,
    run_user_lifecycle_maintenance,
    tenure_months_for,
    utcnow,
)
from ..deps import require_role, get_current_user, resolve_university_scope

router = APIRouter(prefix="/users", tags=["users"])
TEAM_ACCESS_ROLES = ["super_admin", "student_admin", "alumni_admin", "service_recovery"]
TEAM_PROVISIONER_ROLES = ["super_admin", "student_admin", "alumni_admin"]
PASSWORD_RECOVERY_ROLES = ["super_admin", "service_recovery"]
GLOBAL_ONLY_ROLES = {"super_admin", "executive", "director"}
SCOPED_PROVISIONABLE_ROLES = ["student_admin", "alumni_admin", "program_manager", "finance_officer", "students_finance", "committee_member"]
GLOBAL_PROVISIONABLE_ROLES = ["super_admin", *SCOPED_PROVISIONABLE_ROLES]


def _serialize_user(db: Session, user: User, roles: list[str] | None = None) -> UserRead:
    resolved_roles = roles or get_user_roles(db, user)
    tenure_exempt = has_tenure_exemption(resolved_roles)
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
        roles=resolved_roles,
    )


def _ensure_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role:
        return role

    role = Role(name=role_name)
    db.add(role)
    db.flush()
    return role


def _ensure_actor_has_any_role(db: Session, actor: User, required_roles: list[str]) -> None:
    actor_roles = set(get_user_roles(db, actor))
    if not actor_roles.intersection(required_roles):
        raise HTTPException(status_code=403, detail="Insufficient role")


def _allowed_provisioned_roles(db: Session, user: User) -> list[str]:
    user_roles = set(get_user_roles(db, user))
    if "super_admin" in user_roles:
        return [*GLOBAL_PROVISIONABLE_ROLES, "executive", "director"]
    return SCOPED_PROVISIONABLE_ROLES


def _normalize_roles(payload_roles: list[str] | None) -> list[str]:
    normalized_roles: list[str] = []
    for role_name in payload_roles or []:
        normalized_role_name = normalize_role_name(role_name)
        if normalized_role_name not in normalized_roles:
            normalized_roles.append(normalized_role_name)
    return normalized_roles


def _ensure_user_is_visible_to_actor(actor: User, target: User) -> None:
    if target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    if actor.university_id:
        target_scope = target.university_id or (target.member.university_id if target.member else None)
        if target_scope != actor.university_id:
            raise HTTPException(status_code=404, detail="User not found")


def _apply_roles(
    db: Session,
    actor: User,
    target: User,
    normalized_roles: list[str],
    target_university_id: int | None,
) -> list[str]:
    if not normalized_roles:
        raise HTTPException(status_code=400, detail="Select at least one role")

    actor_roles = set(get_user_roles(db, actor))
    if "super_admin" in normalized_roles and "super_admin" not in actor_roles:
        raise HTTPException(status_code=403, detail="Only a super admin can create another super admin")

    if target_university_id is not None and any(role_name in GLOBAL_ONLY_ROLES for role_name in normalized_roles):
        raise HTTPException(status_code=403, detail="Executive, director, and super admin roles are only allowed for global accounts")

    allowed_roles = _allowed_provisioned_roles(db, actor)
    for role_name in normalized_roles:
        if role_name not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"You cannot provision the role {role_name}")

    db.query(UserRole).filter(UserRole.user_id == target.id).delete()
    for role_name in normalized_roles:
        role = _ensure_role(db, role_name)
        db.add(UserRole(user_id=target.id, role_id=role.id))
    db.flush()
    return normalized_roles


def _apply_tenure(target: User, tenure_months: int | None, tenure_starts_on: date | None, tenure_exempt: bool = False) -> None:
    if tenure_exempt:
        target.subject_to_tenure = False
        target.tenure_starts_on = None
        target.tenure_ends_on = None
        return
    try:
        starts_on, ends_on = resolve_tenure_window(tenure_months or DEFAULT_TENURE_MONTHS, tenure_starts_on)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target.subject_to_tenure = True
    target.tenure_starts_on = starts_on
    target.tenure_ends_on = ends_on


def _set_active_state(target: User, is_active: bool, tenure_exempt: bool = False) -> None:
    if is_active:
        if not tenure_exempt and target.subject_to_tenure and target.tenure_ends_on and target.tenure_ends_on <= utcnow().date():
            raise HTTPException(status_code=400, detail="Extend the tenure before reactivating this account")
        target.is_active = True
        target.disabled_at = None
        return

    target.is_active = False
    target.disabled_at = utcnow()


@router.get("/me", response_model=UserRead)
def me(db: Session = Depends(get_db), current=Depends(get_current_user)):
    return _serialize_user(db, current)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), user=Depends(require_role(TEAM_ACCESS_ROLES))):
    _ensure_actor_has_any_role(db, user, TEAM_ACCESS_ROLES)
    run_user_lifecycle_maintenance(db)
    query = db.query(User).filter(User.deleted_at.is_(None)).order_by(User.name.asc().nullslast(), User.email.asc())
    if user.university_id:
        query = query.outerjoin(Member, Member.id == User.member_id).filter(
            or_(
                User.university_id == user.university_id,
                Member.university_id == user.university_id,
            )
        )
    users = query.all()
    results = []
    for item in users:
        roles = get_user_roles(db, item)
        results.append(_serialize_user(db, item, roles=roles))
    return results


@router.post("", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user=Depends(require_role(TEAM_PROVISIONER_ROLES))):
    _ensure_actor_has_any_role(db, user, TEAM_PROVISIONER_ROLES)
    run_user_lifecycle_maintenance(db)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email exists")
    normalized_roles = _normalize_roles(payload.roles)
    target_university_id = resolve_university_scope(user, payload.university_id)
    if user.university_id and target_university_id is None:
        raise HTTPException(status_code=403, detail="Scoped admins cannot create global users")

    new_user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        university_id=target_university_id,
        subject_to_tenure=not has_tenure_exemption(normalized_roles),
        force_password_reset=bool(payload.force_password_reset),
    )
    _apply_tenure(new_user, payload.tenure_months, payload.tenure_starts_on, tenure_exempt=has_tenure_exemption(normalized_roles))
    db.add(new_user)
    try:
        db.flush()
        roles = _apply_roles(db, user, new_user, normalized_roles, target_university_id)
        db.commit()
        db.refresh(new_user)
    except Exception:
        db.rollback()
        raise

    return _serialize_user(db, new_user, roles=roles)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(TEAM_PROVISIONER_ROLES)),
):
    _ensure_actor_has_any_role(db, user, TEAM_PROVISIONER_ROLES)
    run_user_lifecycle_maintenance(db)
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    _ensure_user_is_visible_to_actor(user, target)

    field_names = payload.model_fields_set
    if "email" in field_names and payload.email:
        duplicate = (
            db.query(User)
            .filter(User.email == payload.email, User.id != target.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="Email exists")
        target.email = payload.email

    if "name" in field_names:
        target.name = payload.name

    if "password" in field_names and payload.password:
        target.password_hash = hash_password(payload.password)

    if "force_password_reset" in field_names and payload.force_password_reset is not None:
        target.force_password_reset = payload.force_password_reset

    target_university_id = target.university_id
    if "university_id" in field_names:
        target_university_id = resolve_university_scope(user, payload.university_id)
        if user.university_id and target_university_id is None:
            raise HTTPException(status_code=403, detail="Scoped admins cannot create global users")
        target.university_id = target_university_id

    normalized_roles = get_user_roles(db, target)
    if "roles" in field_names and payload.roles is not None:
        normalized_roles = _apply_roles(db, user, target, _normalize_roles(payload.roles), target_university_id)
    tenure_exempt = has_tenure_exemption(normalized_roles)

    should_update_tenure = target.subject_to_tenure or target.member_id is None or tenure_exempt
    if "tenure_months" in field_names or "tenure_starts_on" in field_names or should_update_tenure:
        current_start = payload.tenure_starts_on if "tenure_starts_on" in field_names else target.tenure_starts_on
        current_months = payload.tenure_months if "tenure_months" in field_names else None
        if not current_months:
            current_months = tenure_months_for(target)
        _apply_tenure(target, current_months or DEFAULT_TENURE_MONTHS, current_start, tenure_exempt=tenure_exempt)

    if "is_active" in field_names and payload.is_active is not None:
        _set_active_state(target, payload.is_active, tenure_exempt=tenure_exempt)
    elif not tenure_exempt and target.is_active and target.subject_to_tenure and target.tenure_ends_on and target.tenure_ends_on <= utcnow().date():
        target.is_active = False
        target.disabled_at = target.disabled_at or utcnow()

    db.commit()
    db.refresh(target)
    return _serialize_user(db, target, roles=normalized_roles)


@router.post("/{user_id}/recover-password", response_model=UserRead)
def recover_user_password(
    user_id: int,
    payload: UserPasswordRecovery,
    db: Session = Depends(get_db),
    user=Depends(require_role(PASSWORD_RECOVERY_ROLES)),
):
    _ensure_actor_has_any_role(db, user, PASSWORD_RECOVERY_ROLES)
    run_user_lifecycle_maintenance(db)
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_user_is_visible_to_actor(user, target)

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    target.password_hash = hash_password(payload.new_password)
    target.force_password_reset = bool(payload.force_password_reset)
    db.commit()
    db.refresh(target)
    return _serialize_user(db, target)
