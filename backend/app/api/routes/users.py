from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models import Member, Role, User, UserRole
from ...schemas import UserCreate, UserRead
from ...core.security import hash_password
from ...services.rbac import get_user_roles, normalize_role_name
from ..deps import require_role, get_current_user, resolve_university_scope

router = APIRouter(prefix="/users", tags=["users"])
TEAM_PROVISIONER_ROLES = ["super_admin", "student_admin", "alumni_admin"]
GLOBAL_ONLY_ROLES = {"super_admin", "executive", "director"}
SCOPED_PROVISIONABLE_ROLES = ["student_admin", "alumni_admin", "program_manager", "finance_officer", "students_finance", "committee_member"]
GLOBAL_PROVISIONABLE_ROLES = ["super_admin", *SCOPED_PROVISIONABLE_ROLES]


def _serialize_user(db: Session, user: User, roles: list[str] | None = None) -> UserRead:
    resolved_roles = roles or get_user_roles(db, user)
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        university_id=user.university_id,
        member_id=str(user.member.id) if user.member else None,
        member_number=user.member.member_id if user.member else None,
        member_status=user.member.status if user.member else None,
        member_university_id=user.member.university_id if user.member else None,
        member_university_name=user.member.university.name if user.member and user.member.university else None,
        donor_interest=bool(user.donor_interest),
        is_active=user.is_active,
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


def _allowed_provisioned_roles(db: Session, user: User) -> list[str]:
    user_roles = set(get_user_roles(db, user))
    if "super_admin" in user_roles:
        return [*GLOBAL_PROVISIONABLE_ROLES, "executive", "director"]
    return SCOPED_PROVISIONABLE_ROLES


@router.get("/me", response_model=UserRead)
def me(db: Session = Depends(get_db), current=Depends(get_current_user)):
    return _serialize_user(db, current)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), user=Depends(require_role(TEAM_PROVISIONER_ROLES))):
    query = db.query(User).order_by(User.name.asc().nullslast(), User.email.asc())
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
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email exists")
    allowed_roles = _allowed_provisioned_roles(db, user)
    target_university_id = resolve_university_scope(user, payload.university_id)
    if user.university_id and target_university_id is None:
        raise HTTPException(status_code=403, detail="Scoped admins cannot create global users")
    normalized_roles: list[str] = []
    for role_name in payload.roles:
        normalized_role_name = normalize_role_name(role_name)
        if normalized_role_name not in normalized_roles:
            normalized_roles.append(normalized_role_name)
    if not normalized_roles:
        raise HTTPException(status_code=400, detail="Select at least one role")
    if target_university_id is not None and any(role_name in GLOBAL_ONLY_ROLES for role_name in normalized_roles):
        raise HTTPException(status_code=403, detail="Executive, director, and super admin roles are only allowed for global accounts")

    for role_name in normalized_roles:
        if role_name not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"You cannot provision the role {role_name}")

    new_user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        university_id=target_university_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    roles = []
    for role_name in normalized_roles:
        role = _ensure_role(db, role_name)
        db.add(UserRole(user_id=new_user.id, role_id=role.id))
        roles.append(role_name)
    db.commit()
    db.refresh(new_user)

    return _serialize_user(db, new_user, roles=roles)
