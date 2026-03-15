from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from ..models import User
from .rbac import get_user_roles

DEFAULT_TENURE_MONTHS = 24
DISABLED_RETENTION_MONTHS = 3
SUPER_ADMIN_ROLE = "super_admin"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def add_months(value: date, months: int) -> date:
    total_month = (value.month - 1) + months
    year = value.year + (total_month // 12)
    month = (total_month % 12) + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def resolve_tenure_window(
    tenure_months: int | None,
    tenure_starts_on: date | None = None,
) -> tuple[date, date]:
    resolved_months = tenure_months or DEFAULT_TENURE_MONTHS
    if resolved_months < 1:
        raise ValueError("Tenure must be at least 1 month")
    starts_on = tenure_starts_on or utcnow().date()
    return starts_on, add_months(starts_on, resolved_months)


def has_tenure_exemption(user_roles: list[str]) -> bool:
    return SUPER_ADMIN_ROLE in user_roles


def deletion_due_on(user: User, tenure_exempt: bool = False) -> date | None:
    if not user.disabled_at or tenure_exempt:
        return None
    return add_months(user.disabled_at.date(), DISABLED_RETENTION_MONTHS)


def tenure_months_for(user: User) -> int | None:
    if not user.tenure_starts_on or not user.tenure_ends_on:
        return None
    return max(
        1,
        ((user.tenure_ends_on.year - user.tenure_starts_on.year) * 12)
        + (user.tenure_ends_on.month - user.tenure_starts_on.month),
    )


def run_user_lifecycle_maintenance(db: Session, now: datetime | None = None) -> None:
    current_time = now or utcnow()
    current_date = current_time.date()
    dirty = False

    users = (
        db.query(User)
        .filter(User.deleted_at.is_(None))
        .all()
    )

    for user in users:
        user_roles = get_user_roles(db, user)
        if has_tenure_exemption(user_roles):
            if user.subject_to_tenure:
                user.subject_to_tenure = False
                dirty = True
            if user.tenure_starts_on is not None:
                user.tenure_starts_on = None
                dirty = True
            if user.tenure_ends_on is not None:
                user.tenure_ends_on = None
                dirty = True
            continue

        if user.subject_to_tenure and user.tenure_ends_on and user.is_active and user.tenure_ends_on <= current_date:
            user.is_active = False
            user.disabled_at = user.disabled_at or current_time
            dirty = True

        if not user.is_active and user.disabled_at and add_months(user.disabled_at.date(), DISABLED_RETENTION_MONTHS) <= current_date:
            user.deleted_at = current_time
            dirty = True

    if dirty:
        db.commit()


def ensure_user_lifecycle_state(db: Session, user: User, now: datetime | None = None) -> User | None:
    if user.deleted_at is not None:
        return None

    current_time = now or utcnow()
    current_date = current_time.date()
    dirty = False

    user_roles = get_user_roles(db, user)
    if has_tenure_exemption(user_roles):
        if user.subject_to_tenure:
            user.subject_to_tenure = False
            dirty = True
        if user.tenure_starts_on is not None:
            user.tenure_starts_on = None
            dirty = True
        if user.tenure_ends_on is not None:
            user.tenure_ends_on = None
            dirty = True
    else:
        if user.subject_to_tenure and user.tenure_ends_on and user.is_active and user.tenure_ends_on <= current_date:
            user.is_active = False
            user.disabled_at = user.disabled_at or current_time
            dirty = True

        if not user.is_active and user.disabled_at and add_months(user.disabled_at.date(), DISABLED_RETENTION_MONTHS) <= current_date:
            user.deleted_at = current_time
            dirty = True

    if dirty:
        db.commit()
        db.refresh(user)

    if user.deleted_at is not None:
        return None
    return user
