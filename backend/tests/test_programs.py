import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.programs import create_program, update_program
from app.db.base import Base
from app.models import Program, University, User
from app.schemas import ProgramCreate, ProgramUpdatePayload


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_program_duration_weeks_is_calculated_from_dates(db_session: Session):
    user = User(email="planner@example.com", name="Planner", password_hash="hashed")
    university = University(name="Example University")
    db_session.add_all([user, university])
    db_session.commit()

    created = create_program(
        ProgramCreate(
            university_id=university.id,
            name="Week of Prayer",
            audience="Students",
            duration_weeks=99,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 14),
        ),
        db=db_session,
        user=user,
    )

    assert created.duration_weeks == 2.0

    updated = update_program(
        created.id,
        ProgramUpdatePayload(
            end_date=date(2026, 1, 21),
            duration_weeks=99,
        ),
        db=db_session,
        user=user,
    )

    stored = db_session.query(Program).filter(Program.id == created.id).first()
    assert stored is not None
    assert updated.duration_weeks == 3.0
    assert stored.duration_weeks == 3.0


def test_program_rejects_end_date_before_start_date(db_session: Session):
    user = User(email="planner@example.com", name="Planner", password_hash="hashed")
    university = University(name="Example University")
    db_session.add_all([user, university])
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_program(
            ProgramCreate(
                university_id=university.id,
                name="Invalid Window Program",
                audience="Students",
                start_date=date(2026, 1, 14),
                end_date=date(2026, 1, 1),
            ),
            db=db_session,
            user=user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Program end date must be on or after the start date"
