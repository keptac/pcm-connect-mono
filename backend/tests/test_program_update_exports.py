import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.program_updates import download_consolidated_report_pdf
from app.db.base import Base
from app.models import Conference, Program, ProgramUpdate, University, User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


async def _read_streaming_response_body(response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


def test_consolidated_report_pdf_downloads_combined_pdf(db_session: Session):
    conference_a = Conference(name="North Zimbabwe Conference", union_name="ZUC")
    conference_b = Conference(name="South Zimbabwe Conference", union_name="ZUC")
    university_a = University(name="Campus A", conference=conference_a)
    university_b = University(name="Campus B", conference=conference_b)
    user = User(email="super-admin@example.com", name="Super Admin", password_hash="hashed")
    program_a = Program(
        university=university_a,
        name="Week of Prayer",
        target_beneficiaries=120,
        duration_weeks=2,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 14),
    )
    program_b = Program(
        university=university_b,
        name="Evangelism Campaign",
        target_beneficiaries=80,
        duration_weeks=1,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 26),
    )
    update_a = ProgramUpdate(
        university=university_a,
        program=program_a,
        title="Week of Prayer",
        event_name="Week of Prayer",
        reporting_period="2026-Q1",
        summary="Campus A reported strong participation and engagement.",
        outcomes="Students requested more follow-up Bible studies.",
        challenges="Sound system failed during one evening session.",
        next_steps="Organize discipleship follow-up groups.",
        beneficiaries_reached=140,
        volunteers_involved=18,
        funds_used=320.0,
    )
    update_b = ProgramUpdate(
        university=university_b,
        program=program_b,
        title="Evangelism Campaign",
        event_name="Evangelism Campaign",
        reporting_period="2026-Q1",
        summary="Campus B combined outreach and literature distribution.",
        outcomes="Several community visitors returned for Sabbath worship.",
        challenges="Transport costs reduced the planned field coverage.",
        next_steps="Secure transport earlier for the next campaign.",
        beneficiaries_reached=95,
        volunteers_involved=11,
        funds_used=210.0,
    )
    db_session.add_all([conference_a, conference_b, university_a, university_b, user, program_a, program_b, update_a, update_b])
    db_session.commit()

    response = download_consolidated_report_pdf(
        reporting_period="2026-Q1",
        db=db_session,
        user=user,
    )

    body = asyncio.run(_read_streaming_response_body(response))

    assert response.headers["content-disposition"] == 'attachment; filename="impact-report-consolidated_all-campuses_2026-Q1.pdf"'
    assert body.startswith(b"%PDF")
    assert len(body) > 1000
