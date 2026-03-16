import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import FUNDING_ROLES, FUNDING_WRITE_ROLES, require_role
from app.api.routes.auth import change_password, login
from app.api.routes.funding import create_funding_record
from app.api.routes.users import create_user, list_users, recover_user_password, update_user
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.models import FundingRecord, Role, University, User, UserRole
from app.schemas import ChangePasswordRequest, FundingRecordCreate, LoginRequest, UserCreate, UserPasswordRecovery, UserUpdate
from app.services.user_lifecycle import run_user_lifecycle_maintenance


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_role(db_session: Session, user: User, role_name: str) -> None:
    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()


def test_only_super_admin_can_create_super_admin(db_session: Session):
    provisioner = User(
        email="student-admin@example.com",
        name="Student Admin",
        password_hash="hashed",
    )
    db_session.add(provisioner)
    db_session.commit()
    add_role(db_session, provisioner, "student_admin")

    with pytest.raises(HTTPException) as exc_info:
        create_user(
            UserCreate(
                email="new-super-admin@example.com",
                name="New Super Admin",
                password="secret123",
                roles=["super_admin"],
            ),
            db=db_session,
            user=provisioner,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only a super admin can create another super admin"
    assert db_session.query(User).filter(User.email == "new-super-admin@example.com").first() is None


def test_super_admin_can_create_super_admin(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    db_session.add(provisioner)
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")

    created = create_user(
        UserCreate(
            email="new-super-admin@example.com",
            name="New Super Admin",
            password="secret123",
            roles=["super_admin"],
        ),
        db=db_session,
        user=provisioner,
    )

    assert created.email == "new-super-admin@example.com"
    assert created.roles == ["super_admin"]
    assert created.subject_to_tenure is False
    assert created.tenure_starts_on is None
    assert created.tenure_ends_on is None
    stored_user = db_session.query(User).filter(User.email == "new-super-admin@example.com").first()
    assert stored_user is not None


def test_created_team_user_gets_default_tenure(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    db_session.add(provisioner)
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")

    created = create_user(
        UserCreate(
            email="finance@example.com",
            name="Finance Officer",
            password="secret123",
            roles=["finance_officer"],
        ),
        db=db_session,
        user=provisioner,
    )

    stored_user = db_session.query(User).filter(User.email == "finance@example.com").first()
    assert stored_user is not None
    assert created.roles == ["finance_officer"]
    assert created.subject_to_tenure is True
    assert created.tenure_months == 24
    assert created.tenure_starts_on is not None
    assert created.tenure_ends_on is not None
    assert stored_user.subject_to_tenure is True
    assert stored_user.tenure_starts_on == created.tenure_starts_on
    assert stored_user.tenure_ends_on == created.tenure_ends_on


def test_created_team_user_can_require_password_reset_at_login(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    db_session.add(provisioner)
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")

    created = create_user(
        UserCreate(
            email="team-reset@example.com",
            name="Reset Required",
            password="secret123",
            roles=["student_admin"],
            force_password_reset=True,
        ),
        db=db_session,
        user=provisioner,
    )

    assert created.force_password_reset is True

    session = login(
        LoginRequest(email="team-reset@example.com", password="secret123"),
        db=db_session,
    )
    assert session.password_reset_required is True


def test_service_recovery_cannot_provision_team_accounts(db_session: Session):
    recovery_user = User(
        email="adam@pcm.service",
        name="PCM Recovery Service",
        password_hash="hashed",
    )
    db_session.add(recovery_user)
    db_session.commit()
    add_role(db_session, recovery_user, "service_recovery")

    with pytest.raises(HTTPException) as exc_info:
        create_user(
            UserCreate(
                email="blocked@example.com",
                name="Blocked User",
                password="secret123",
                roles=["student_admin"],
            ),
            db=db_session,
            user=recovery_user,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient role"


def test_secretary_cannot_provision_team_accounts(db_session: Session):
    university = University(name="Example University")
    provisioner = User(
        email="secretary@example.com",
        name="Campus Secretary",
        password_hash="hashed",
        university=university,
    )
    db_session.add_all([university, provisioner])
    db_session.commit()
    add_role(db_session, provisioner, "secretary")

    with pytest.raises(HTTPException) as exc_info:
        create_user(
            UserCreate(
                email="assistant-secretary@example.com",
                name="Assistant Secretary",
                password="secret123",
                roles=["secretary"],
                university_id=university.id,
            ),
            db=db_session,
            user=provisioner,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient role"


def test_service_recovery_can_reset_password_and_force_change(db_session: Session):
    recovery_user = User(
        email="adam@pcm.service",
        name="PCM Recovery Service",
        password_hash="hashed",
    )
    target_user = User(
        email="locked-out-admin@example.com",
        name="Locked Out Admin",
        password_hash=hash_password("old-secret123"),
        force_password_reset=False,
    )
    db_session.add_all([recovery_user, target_user])
    db_session.commit()
    add_role(db_session, recovery_user, "service_recovery")
    add_role(db_session, target_user, "super_admin")

    updated = recover_user_password(
        target_user.id,
        UserPasswordRecovery(new_password="temp-secret123", force_password_reset=True),
        db=db_session,
        user=recovery_user,
    )

    db_session.refresh(target_user)
    assert updated.force_password_reset is True
    assert verify_password("temp-secret123", target_user.password_hash)

    session = login(
        LoginRequest(email="locked-out-admin@example.com", password="temp-secret123"),
        db=db_session,
    )
    assert session.password_reset_required is True


def test_team_user_list_hides_seeded_service_accounts(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    system_admin = User(
        email="admin@pcm.local",
        name="System Admin",
        password_hash="hashed",
        is_system_admin=True,
    )
    recovery_user = User(
        email="adam@pcm.service",
        name="PCM Recovery Service",
        password_hash="hashed",
    )
    visible_user = User(
        email="team@example.com",
        name="Team User",
        password_hash="hashed",
        subject_to_tenure=True,
        tenure_starts_on=date(2026, 1, 1),
        tenure_ends_on=date(2028, 1, 1),
    )
    db_session.add_all([provisioner, system_admin, recovery_user, visible_user])
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")
    add_role(db_session, system_admin, "super_admin")
    add_role(db_session, recovery_user, "service_recovery")
    add_role(db_session, visible_user, "student_admin")

    listed_users = list_users(db=db_session, user=provisioner)
    listed_names = {item.name for item in listed_users}

    assert "System Admin" not in listed_names
    assert "PCM Recovery Service" not in listed_names
    assert "Team User" in listed_names


def test_expired_tenure_disables_then_hides_user_from_team_list(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    teammate = User(
        email="program-manager@example.com",
        name="Program Manager",
        password_hash="hashed",
        subject_to_tenure=True,
        tenure_starts_on=date(2022, 1, 1),
        tenure_ends_on=date(2024, 1, 1),
        is_active=True,
    )
    db_session.add_all([provisioner, teammate])
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")
    add_role(db_session, teammate, "program_manager")

    run_user_lifecycle_maintenance(db_session, now=datetime(2024, 1, 2, 8, 0, 0))
    db_session.refresh(teammate)
    assert teammate.is_active is False
    assert teammate.disabled_at is not None
    assert teammate.deleted_at is None

    run_user_lifecycle_maintenance(db_session, now=datetime(2024, 4, 3, 8, 0, 0))
    db_session.refresh(teammate)
    assert teammate.deleted_at is not None

    listed_users = list_users(db=db_session, user=provisioner)
    assert all(item.email != "program-manager@example.com" for item in listed_users)


def test_super_admin_role_is_exempt_from_tenure_maintenance(db_session: Session):
    super_admin = User(
        email="admin@pcm.local",
        name="Super Admin",
        password_hash="hashed",
        is_active=False,
        subject_to_tenure=True,
        tenure_starts_on=date(2020, 1, 1),
        tenure_ends_on=date(2022, 1, 1),
        disabled_at=datetime(2025, 9, 1, 8, 0, 0),
    )
    db_session.add(super_admin)
    db_session.commit()
    add_role(db_session, super_admin, "super_admin")

    run_user_lifecycle_maintenance(db_session, now=datetime(2026, 1, 1, 8, 0, 0))
    db_session.refresh(super_admin)

    assert super_admin.is_active is False
    assert super_admin.deleted_at is None
    assert super_admin.disabled_at is not None
    assert super_admin.subject_to_tenure is False
    assert super_admin.tenure_starts_on is None
    assert super_admin.tenure_ends_on is None


def test_update_user_can_extend_tenure_and_reactivate_account(db_session: Session):
    provisioner = User(
        email="super-admin@example.com",
        name="Super Admin",
        password_hash="hashed",
    )
    teammate = User(
        email="team@example.com",
        name="Team User",
        password_hash="hashed",
        subject_to_tenure=True,
        tenure_starts_on=date(2024, 1, 1),
        tenure_ends_on=date(2026, 1, 1),
        is_active=False,
        disabled_at=datetime(2026, 1, 2, 8, 0, 0),
    )
    db_session.add_all([provisioner, teammate])
    db_session.commit()
    add_role(db_session, provisioner, "super_admin")
    add_role(db_session, teammate, "student_admin")

    updated = update_user(
        teammate.id,
        UserUpdate(
            tenure_starts_on=date(2026, 1, 1),
            tenure_months=24,
            is_active=True,
        ),
        db=db_session,
        user=provisioner,
    )

    assert updated.is_active is True
    assert updated.disabled_at is None
    assert updated.tenure_starts_on == date(2026, 1, 1)
    assert updated.tenure_ends_on == date(2028, 1, 1)


def test_change_password_clears_force_reset_flag(db_session: Session):
    user = User(
        email="reset-me@example.com",
        name="Reset Me",
        password_hash=hash_password("secret123"),
        force_password_reset=True,
    )
    db_session.add(user)
    db_session.commit()

    updated = change_password(
        ChangePasswordRequest(current_password="secret123", new_password="new-secret123"),
        db=db_session,
        user=user,
    )

    db_session.refresh(user)
    assert updated.force_password_reset is False
    assert user.force_password_reset is False
    assert verify_password("new-secret123", user.password_hash)


def test_executive_can_record_treasury_entry(db_session: Session):
    executive_user = User(
        email="executive@example.com",
        name="Executive User",
        password_hash="hashed",
    )
    university = University(name="Test University")
    db_session.add_all([executive_user, university])
    db_session.commit()
    add_role(db_session, executive_user, "executive")

    guard = require_role(FUNDING_WRITE_ROLES)
    assert guard(db=db_session, user=executive_user) is executive_user

    created = create_funding_record(
        FundingRecordCreate(
            university_id=university.id,
            source_name="Treasury receipt",
            entry_type="donation",
            flow_direction="inflow",
            receipt_category="Donation",
            reporting_window="weekly",
            amount=245.0,
            currency="USD",
            transaction_date=date(2026, 3, 15),
            channel="cash",
            designation="Executive allocation",
        ),
        db=db_session,
        user=executive_user,
    )

    stored = db_session.query(FundingRecord).filter(FundingRecord.id == created.id).first()
    assert stored is not None
    assert created.university_id == university.id
    assert created.recorded_by == executive_user.id
    assert created.receipt_category == "Donation"


def test_secretary_cannot_access_funding_scope(db_session: Session):
    secretary_user = User(
        email="secretary@example.com",
        name="Campus Secretary",
        password_hash="hashed",
    )
    db_session.add(secretary_user)
    db_session.commit()
    add_role(db_session, secretary_user, "secretary")

    guard = require_role(FUNDING_ROLES)
    with pytest.raises(HTTPException) as exc_info:
        guard(db=db_session, user=secretary_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient role"
