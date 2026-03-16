import asyncio
import json
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.api.routes.program_updates import _attachment_response_rows, _require_meeting_minutes, _serialize, download_consolidated_report_pdf
from app.core.config import settings
from app.db.base import Base
from app.models import Conference, Program, ProgramUpdate, University, User
from app.services.program_update_consolidated_exports import _build_consolidated_narrative_sections
from app.services.program_update_exports import (
    _build_cover_metric_items,
    _build_detailed_metric_items,
    _build_styles,
    _extract_doc_pages,
    _extract_docx_blocks,
    _extract_pdf_pages,
    _volunteer_helper_text,
    build_program_update_pdf,
)


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
        reporting_date=date(2026, 3, 12),
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
        reporting_date=date(2026, 3, 18),
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
        reporting_date=date(2026, 3, 10),
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


def test_serialize_includes_reporting_date(db_session: Session):
    conference = Conference(name="East Zimbabwe Conference", union_name="ZUC")
    university = University(name="Campus C", conference=conference)
    update = ProgramUpdate(
        university=university,
        title="Health Expo",
        event_name="Health Expo",
        reporting_period="2026-Q1",
        reporting_date=date(2026, 3, 22),
        summary="Health screenings were completed.",
    )
    db_session.add_all([conference, university, update])
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

    serialized = _serialize(update, request)

    assert serialized.reporting_date == date(2026, 3, 22)


def test_meeting_updates_require_minutes():
    with pytest.raises(HTTPException) as exc:
        _require_meeting_minutes("Meeting", False)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Meeting updates require uploaded minutes"


def test_meeting_download_reformats_minutes_into_pcm_branded_pdf(db_session: Session, tmp_path: Path):
    previous_upload_dir = settings.upload_dir
    settings.upload_dir = str(tmp_path)
    try:
        source_pdf = tmp_path / "minutes-source.pdf"
        source_canvas = canvas.Canvas(str(source_pdf))
        source_text = source_canvas.beginText(72, 770)
        for line in ["Executive Committee Meeting", "Opening prayer", "Agenda adopted", "Closing remarks"]:
            source_text.textLine(line)
        source_canvas.drawText(source_text)
        source_canvas.save()

        conference = Conference(name="North Zimbabwe Conference", union_name="ZUC")
        university = University(name="PCM Office", conference=conference)
        submitter = User(email="secretary@example.com", name="Campus Secretary", password_hash="hashed")
        db_session.add_all([conference, university, submitter])
        db_session.flush()
        update = ProgramUpdate(
            university=university,
            title="Meeting",
            event_name="Meeting",
            reporting_period="2026-Q1",
            reporting_date=date(2026, 3, 14),
            summary="Monthly executive meeting minutes.",
            attachments_json=json.dumps(
                [
                    {
                        "name": "minutes-source.pdf",
                        "stored_name": source_pdf.name,
                        "content_type": "application/pdf",
                        "size_bytes": source_pdf.stat().st_size,
                        "category": "minutes",
                        "meeting_date": "2026-03-14",
                        "venue": "PCM Office Boardroom",
                        "notes": "Approved minutes",
                    }
                ]
            ),
            submitted_by=submitter.id,
        )
        db_session.add(update)
        db_session.commit()

        pdf_bytes = build_program_update_pdf(update)
        extracted_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)

        assert "Meeting Minutes" in extracted_text
        assert "Campus Secretary" in extracted_text
        assert "PCM Office Boardroom" in extracted_text
        assert "Agenda adopted" in extracted_text
    finally:
        settings.upload_dir = previous_upload_dir


def test_meeting_download_handles_long_minutes_content_without_layout_error(db_session: Session, monkeypatch):
    conference = Conference(name="North Zimbabwe Conference", union_name="ZUC")
    university = University(name="PCM Office", conference=conference)
    submitter = User(email="secretary@example.com", name="Campus Secretary", password_hash="hashed")
    db_session.add_all([conference, university, submitter])
    db_session.flush()

    update = ProgramUpdate(
        university=university,
        title="Meeting",
        event_name="Meeting",
        reporting_period="2026-Q1",
        reporting_date=date(2026, 3, 14),
        summary="Monthly executive meeting minutes.",
        submitted_by=submitter.id,
    )
    db_session.add(update)
    db_session.commit()

    long_minutes_text = "\n".join(
        f"{index}. {'Agenda item and discussion notes ' * 8}".strip() for index in range(1, 180)
    )
    monkeypatch.setattr(
        "app.services.program_update_exports._extract_meeting_minutes_documents",
        lambda update: [
            {
                "name": "minutes-march.docx",
                "meeting_date": "2026-03-14",
                "venue": "PCM Office Boardroom",
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "pages": [long_minutes_text],
            }
        ],
    )

    pdf_bytes = build_program_update_pdf(update)
    reader = PdfReader(BytesIO(pdf_bytes))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) >= 3
    assert "Meeting Minutes" in extracted_text
    assert "Agenda item and discussion notes" in extracted_text


def test_extract_docx_blocks_preserve_headings_bullets_and_tables(tmp_path: Path):
    docx_path = tmp_path / "minutes-structured.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:rPr><w:b/></w:rPr><w:t>Action Points</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:numPr><w:ilvl w:val="1"/></w:numPr></w:pPr>
      <w:r><w:t>Review previous minutes</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Item</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Owner</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Prayer roster</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Secretary</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    with ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    blocks = _extract_docx_blocks(docx_path)

    assert blocks[0]["type"] == "heading"
    assert "<b>Action Points</b>" in blocks[0]["markup"]
    assert blocks[1]["type"] == "bullet"
    assert blocks[1]["level"] == 1
    assert "Review previous minutes" in blocks[1]["markup"]
    assert blocks[2]["type"] == "table"
    assert blocks[2]["header"] is True
    assert "Prayer roster" in blocks[2]["rows"][1][0]["markup"]
    assert "Secretary" in blocks[2]["rows"][1][1]["markup"]


def test_meeting_download_renders_structured_minutes_blocks(db_session: Session, monkeypatch):
    conference = Conference(name="North Zimbabwe Conference", union_name="ZUC")
    university = University(name="PCM Office", conference=conference)
    submitter = User(email="secretary@example.com", name="Campus Secretary", password_hash="hashed")
    db_session.add_all([conference, university, submitter])
    db_session.flush()

    update = ProgramUpdate(
        university=university,
        title="Meeting",
        event_name="Meeting",
        reporting_period="2026-Q1",
        reporting_date=date(2026, 3, 14),
        summary="Monthly executive meeting minutes.",
        submitted_by=submitter.id,
    )
    db_session.add(update)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.program_update_exports._extract_meeting_minutes_documents",
        lambda update: [
            {
                "name": "minutes-march.docx",
                "meeting_date": "2026-03-14",
                "venue": "PCM Office Boardroom",
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "blocks": [
                    {"type": "heading", "markup": "<b>Action Points</b>"},
                    {"type": "bullet", "level": 1, "markup": "Review previous minutes"},
                    {
                        "type": "table",
                        "header": True,
                        "rows": [
                            [{"markup": "<b>Item</b>", "has_bold": True}, {"markup": "<b>Owner</b>", "has_bold": True}],
                            [{"markup": "Prayer roster", "has_bold": False}, {"markup": "Secretary", "has_bold": False}],
                        ],
                    },
                ],
            }
        ],
    )

    pdf_bytes = build_program_update_pdf(update)
    extracted_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)

    assert "Action Points" in extracted_text
    assert "Review previous minutes" in extracted_text
    assert "Prayer roster" in extracted_text
    assert "Secretary" in extracted_text


def test_extract_pdf_pages_uses_ocr_when_embedded_text_is_missing(monkeypatch):
    monkeypatch.setattr("app.services.program_update_exports._extract_pdf_text_pages", lambda path: [])
    monkeypatch.setattr("app.services.program_update_exports._extract_pdf_ocr_pages", lambda path: ["Scanned committee minutes"])

    pages = _extract_pdf_pages(Path("minutes.pdf"))

    assert pages == ["Scanned committee minutes"]


def test_extract_doc_pages_uses_legacy_doc_extractor(monkeypatch):
    monkeypatch.setattr("app.services.program_update_exports._run_legacy_doc_extractor", lambda path: "Opening prayer\n\nAgenda adopted")

    pages = _extract_doc_pages(Path("minutes.doc"))

    assert len(pages) == 1
    assert "Agenda adopted" in pages[0]
