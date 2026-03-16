import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.api.routes.program_updates import _attachment_response_rows, _ensure_meeting_update_has_minutes, download_consolidated_report_pdf
from app.db.base import Base
from app.models import Conference, Program, ProgramUpdate, University, User
from app.services.program_update_consolidated_exports import _build_consolidated_narrative_sections
from app.services.program_update_exports import _build_cover_metric_items, _build_detailed_metric_items, _build_styles, _volunteer_helper_text


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


def test_consolidated_narrative_sections_flatten_all_narrative_groups():
    styles = _build_styles()
    summary = {
        "section_entries": {
            "summary": [{"meta": "Campus D | Summary Event | 2026-Q1", "text": "Highlight one"}],
            "outcomes": [{"meta": "Campus A | Week of Prayer | 2026-Q1", "text": "Outcome one"}],
            "challenges": [{"meta": "Campus B | Evangelism Campaign | 2026-Q1", "text": "Challenge one"}],
            "next_steps": [{"meta": "Campus C | Discipleship Program | 2026-Q1", "text": "Next step one"}],
        }
    }

    sections = _build_consolidated_narrative_sections(summary, styles)
    bullet_cards = [item for item in sections if item.__class__.__name__ == "Table"]

    assert len(bullet_cards) == 4
    assert bullet_cards[0]._cellvalues[0][0].text == "&bull; Highlight one"
    assert bullet_cards[1]._cellvalues[0][0].text == "&bull; Outcome one"
    assert bullet_cards[2]._cellvalues[0][0].text == "&bull; Challenge one"
    assert bullet_cards[3]._cellvalues[0][0].text == "&bull; Next step one"


def test_report_wording_uses_missionary_and_visitor_labels():
    metrics_without_target = {
        "expected": 0,
        "actual": 100,
        "volunteers": 10,
        "funds_used": 50.0,
        "variance": None,
        "achievement_rate": None,
        "attendees_per_volunteer": 10.0,
    }
    cover_items = _build_cover_metric_items(metrics_without_target)

    assert cover_items[1]["helper"] == "Reported visitors or participation."
    assert cover_items[2]["label"] == "Missionaries"
    assert cover_items[3]["label"] == "Missionary coverage"
    assert cover_items[3]["helper"] == "Missionaries relative to reported visitors."

    detailed_items = _build_detailed_metric_items(metrics_without_target)

    assert detailed_items[0]["helper"] == "Planned visitors or reach."
    assert detailed_items[1]["helper"] == "Reported visitors captured in the update."
    assert detailed_items[2]["label"] == "Missionaries"
    assert detailed_items[3]["helper"] == "Average visitors supported by each missionary."
    assert _volunteer_helper_text(metrics_without_target) == "About 1 missionary supported every 10 visitors."


def test_attachment_response_rows_include_meeting_minutes_metadata(db_session: Session):
    conference = Conference(name="North Zimbabwe Conference", union_name="ZUC")
    university = University(name="Campus A", conference=conference)
    user = User(email="coordinator@example.com", name="Coordinator", password_hash="hashed")
    update = ProgramUpdate(
        university=university,
        title="Committee Update",
        event_name="Committee Meeting",
        reporting_period="2026-Q1",
        summary="Monthly committee meeting completed.",
        attachments_json=json.dumps(
            [
                {
                    "name": "minutes-march.pdf",
                    "stored_name": "minutes-march.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 2048,
                    "category": "minutes",
                    "meeting_date": "2026-03-10",
                    "venue": "Senate Room",
                    "notes": "Approved committee minutes",
                }
            ]
        ),
        submitted_by=1,
    )
    db_session.add_all([conference, university, user, update])
    db_session.commit()

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/program-updates",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
            "query_string": b"",
        }
    )

    attachments = _attachment_response_rows(update, request)

    assert attachments[0]["category"] == "minutes"
    assert attachments[0]["meeting_date"] == "2026-03-10"
    assert attachments[0]["venue"] == "Senate Room"
    assert attachments[0]["notes"] == "Approved committee minutes"


def test_meeting_updates_require_uploaded_minutes():
    with pytest.raises(HTTPException) as exc_info:
        _ensure_meeting_update_has_minutes("Meeting")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Meeting updates require uploaded meeting minutes"


def test_meeting_updates_accept_existing_minutes_attachments():
    _ensure_meeting_update_has_minutes(
        "Meeting",
        kept_attachments=[
            {
                "name": "minutes.pdf",
                "stored_name": "minutes.pdf",
                "category": "minutes",
            }
        ],
    )
