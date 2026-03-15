from typing import Iterable
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from ..models import User, UserRole, Role


def normalize_role_name(role_name: str) -> str:
    return "student_admin" if role_name == "students_admin" else role_name


def get_user_roles(db: Session, user: User) -> list[str]:
    roles = []
    for user_role in user.roles:
        role = db.get(Role, user_role.role_id)
        if role:
            normalized_role = normalize_role_name(role.name)
            if normalized_role not in roles:
                roles.append(normalized_role)
    return roles


def require_roles(required: Iterable[str], user_roles: list[str]) -> None:
    if not set(required).intersection(set(user_roles)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
