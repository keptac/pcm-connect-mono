import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.admin import audit_logs
from app.api.routes.universities import delete_university
from app.db.base import Base
from app.models import AuditLog, Member, Role, University, User, UserRole


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


def test_delete_university_removes_empty_campus_and_logs_action(db_session: Session):
    admin = User(email="admin@example.com", name="Admin", password_hash="hashed")
    university = University(name="Example University")
    db_session.add_all([admin, university])
    db_session.commit()
    add_role(db_session, admin, "super_admin")

    result = delete_university(university.id, db=db_session, user=admin)

    assert result == {"status": "deleted"}
    assert db_session.query(University).filter(University.id == university.id).first() is None
    audit_entry = db_session.query(AuditLog).filter(AuditLog.entity == "university", AuditLog.action == "delete").first()
    assert audit_entry is not None
    assert audit_entry.entity_id == str(university.id)


def test_delete_university_blocks_when_linked_members_exist(db_session: Session):
    admin = User(email="admin@example.com", name="Admin", password_hash="hashed")
    university = University(name="Example University")
    member = Member(university=university, first_name="Tariro", last_name="Moyo", member_id="PCM-10")
    db_session.add_all([admin, university, member])
    db_session.commit()
    add_role(db_session, admin, "super_admin")

    with pytest.raises(HTTPException) as exc_info:
        delete_university(university.id, db=db_session, user=admin)

    assert exc_info.value.status_code == 400
    assert "members (1)" in str(exc_info.value.detail)
    assert db_session.query(University).filter(University.id == university.id).first() is not None


def test_audit_logs_include_actor_name_and_number(db_session: Session):
    university = University(name="Example University")
    admin = User(email="admin@example.com", name="Ada Moyo", password_hash="hashed")
    member = Member(university=university, first_name="Ada", last_name="Moyo", member_id="PCM-001")
    admin.member = member
    db_session.add_all([university, admin])
    db_session.commit()
    add_role(db_session, admin, "super_admin")

    db_session.add(
        AuditLog(
            actor_user_id=admin.id,
            action="update",
            entity="program",
            entity_id="7",
            meta_json=json.dumps({"name": "Leadership Forum"}),
        )
    )
    db_session.commit()

    logs = audit_logs(db=db_session, user=admin)

    assert len(logs) == 1
    assert logs[0].actor_name == "Ada Moyo"
    assert logs[0].actor_number == "PCM-001"
