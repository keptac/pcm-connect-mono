import json
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ...core.config import settings
from ...db.session import get_db
from ...models import MandatoryProgram, Program, ProgramUpdate, ReportingPeriod, University
from ...schemas import (
    CondensedMissionReportRead,
    ProgramImpactUpdateCreate,
    ProgramImpactUpdatePatch,
    ProgramImpactUpdateRead,
)
from ...services.audit_log import log_action
from ...services.program_update_consolidated_exports import build_consolidated_program_update_pdf
from ...services.program_update_exports import build_program_update_pdf, build_program_update_report_pack
from ..deps import GENERAL_USER_ROLES, PROGRAM_ROLES, require_role, resolve_university_scope

router = APIRouter(prefix="/program-updates", tags=["program-updates"])


def _load_attachments(update: ProgramUpdate) -> list[dict]:
    if not update.attachments_json:
        return []
    try:
        parsed = json.loads(update.attachments_json)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _attachment_response_rows(update: ProgramUpdate, request: Request) -> list[dict]:
    base_url = str(request.base_url).rstrip("/")
    rows = []
    for item in _load_attachments(update):
        stored_name = item.get("stored_name") or item.get("path") or ""
        url = item.get("url") or f"{base_url}/uploads/{stored_name}"
        rows.append(
            {
                "name": item.get("name") or stored_name,
                "stored_name": stored_name,
                "url": url,
                "content_type": item.get("content_type"),
                "size_bytes": item.get("size_bytes"),
                "category": item.get("category"),
                "meeting_date": item.get("meeting_date"),
                "venue": item.get("venue"),
                "notes": item.get("notes"),
            }
        )
    return rows


def _delete_attachment_files(attachments: list[dict]) -> None:
    for item in attachments:
        stored_name = item.get("stored_name") or item.get("path")
        if not stored_name:
            continue
        target = Path(settings.upload_dir) / stored_name
        if target.exists():
            target.unlink()


async def _save_attachments(files: list[UploadFile], metadata: dict | None = None) -> list[dict]:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    allowed_extensions = {
        ext.strip().lower()
        for ext in settings.allowed_upload_extensions.split(",")
        if ext.strip()
    }
    max_bytes = settings.max_upload_mb * 1024 * 1024
    saved = []

    for file in files:
        if not file.filename:
            continue
        suffix = Path(file.filename).suffix.lower().lstrip(".")
        if suffix not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Invalid file type for {file.filename}")

        content = await file.read()
        size_bytes = len(content)
        if size_bytes > max_bytes:
            raise HTTPException(status_code=400, detail=f"{file.filename} exceeds the {settings.max_upload_mb}MB upload limit")

        stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex}.{suffix}"
        destination = Path(settings.upload_dir) / stored_name
        destination.write_bytes(content)

        row = {
            "name": file.filename,
            "stored_name": stored_name,
            "content_type": file.content_type,
            "size_bytes": size_bytes,
        }
        if metadata:
            row.update({key: value for key, value in metadata.items() if value is not None})
        saved.append(row)
    return saved


def _to_optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _to_optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _to_optional_text(value):
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_reporting_date(reporting_date: date | None) -> date:
    if not reporting_date:
        raise HTTPException(status_code=400, detail="Reporting date is required")
    return reporting_date


def _is_meeting_event_name(event_name: str | None) -> bool:
    return (event_name or "").strip().lower() == "meeting"


def _require_meeting_minutes(event_name: str | None, has_minutes: bool) -> None:
    if _is_meeting_event_name(event_name) and not has_minutes:
        raise HTTPException(status_code=400, detail="Meeting updates require uploaded minutes")


def _parse_meeting_minutes_metadata(form) -> dict | None:
    meeting_date_value = _to_optional_text(form.get("meeting_minutes_date"))
    venue = _to_optional_text(form.get("meeting_minutes_venue"))
    notes = _to_optional_text(form.get("meeting_minutes_notes"))

    if not any([meeting_date_value, venue, notes]):
        return None
    if not meeting_date_value:
        raise HTTPException(status_code=400, detail="Meeting date is required for meeting minutes")
    if not venue:
        raise HTTPException(status_code=400, detail="Venue is required for meeting minutes")

    try:
        normalized_meeting_date = date.fromisoformat(meeting_date_value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Meeting date must be a valid date") from exc

    return {
        "category": "minutes",
        "meeting_date": normalized_meeting_date,
        "venue": venue,
        "notes": notes,
    }


def _apply_meeting_minutes_metadata(attachments: list[dict], metadata: dict | None) -> list[dict]:
    if not metadata:
        return attachments

    updated_rows = []
    for item in attachments:
        if item.get("category") == "minutes":
            updated_rows.append(
                {
                    **item,
                    "category": metadata["category"],
                    "meeting_date": metadata["meeting_date"],
                    "venue": metadata["venue"],
                    "notes": metadata.get("notes"),
                }
            )
        else:
            updated_rows.append(item)
    return updated_rows


async def _parse_payload_from_request(request: Request, patch: bool = False):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        data = await request.json()
        model = ProgramImpactUpdatePatch if patch else ProgramImpactUpdateCreate
        return model(**data), [], [], None, None

    form = await request.form()
    attachments = [item for item in form.getlist("attachments") if getattr(item, "filename", None)]
    meeting_minutes_attachments = [item for item in form.getlist("meeting_minutes_attachments") if getattr(item, "filename", None)]
    existing_attachments = None
    meeting_minutes_metadata = _parse_meeting_minutes_metadata(form)
    if meeting_minutes_attachments and not meeting_minutes_metadata:
        raise HTTPException(status_code=400, detail="Meeting minutes require both the meeting date and venue")
    if patch and form.get("existing_attachments_json"):
        try:
            existing_attachments = json.loads(str(form.get("existing_attachments_json")))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid attachment metadata") from exc

    try:
        if patch:
            data = {}
            for field in [
                "university_id",
                "program_id",
                "title",
                "event_name",
                "event_detail",
                "reporting_period",
                "reporting_date",
                "summary",
                "outcomes",
                "challenges",
                "next_steps",
                "beneficiaries_reached",
                "volunteers_involved",
                "funds_used",
            ]:
                if field not in form:
                    continue
                value = form.get(field)
                if field in {"university_id", "program_id", "beneficiaries_reached", "volunteers_involved"}:
                    data[field] = _to_optional_int(value)
                elif field == "funds_used":
                    data[field] = _to_optional_float(value)
                else:
                    data[field] = value
            return ProgramImpactUpdatePatch(**data), attachments, meeting_minutes_attachments, existing_attachments, meeting_minutes_metadata

        data = {
            "university_id": int(form.get("university_id")),
            "program_id": _to_optional_int(form.get("program_id")),
            "title": form.get("title") or None,
            "event_name": str(form.get("event_name") or ""),
            "event_detail": form.get("event_detail") or None,
            "reporting_period": str(form.get("reporting_period") or ""),
            "reporting_date": form.get("reporting_date"),
            "summary": str(form.get("summary") or ""),
            "outcomes": form.get("outcomes") or None,
            "challenges": form.get("challenges") or None,
            "next_steps": form.get("next_steps") or None,
            "beneficiaries_reached": _to_optional_int(form.get("beneficiaries_reached")) or 0,
            "volunteers_involved": _to_optional_int(form.get("volunteers_involved")) or 0,
            "funds_used": _to_optional_float(form.get("funds_used")),
        }
        return ProgramImpactUpdateCreate(**data), attachments, meeting_minutes_attachments, None, meeting_minutes_metadata
    except (TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid update submission") from exc


def _normalize_event_fields(
    db: Session,
    event_name: str | None,
    event_detail: str | None,
    fallback_title: str | None = None,
    allow_inactive_selected: bool = False,
) -> tuple[str, str | None, str]:
    normalized_event_name = (event_name or "").strip()
    normalized_event_detail = (event_detail or "").strip() or None
    if not normalized_event_name:
        raise HTTPException(status_code=400, detail="Event is required")

    active_event_configs = (
        db.query(MandatoryProgram)
        .filter(MandatoryProgram.program_type == "event", MandatoryProgram.is_active.is_(True))
        .all()
    )
    event_config = next((item for item in active_event_configs if item.name == normalized_event_name), None)
    if active_event_configs and not event_config and allow_inactive_selected:
        event_config = (
            db.query(MandatoryProgram)
            .filter(
                MandatoryProgram.program_type == "event",
                MandatoryProgram.name == normalized_event_name,
            )
            .first()
        )
    if active_event_configs and not event_config:
        raise HTTPException(status_code=400, detail="Selected event is not in mandatory programs")

    requires_detail = bool(event_config.allow_other_detail) if event_config else normalized_event_name.lower().startswith("other")
    if requires_detail and not normalized_event_detail:
        raise HTTPException(status_code=400, detail="Specify the event for the selected Event option")
    if not requires_detail:
        normalized_event_detail = None

    title = normalized_event_detail if requires_detail else normalized_event_name
    if fallback_title and not title:
        title = fallback_title.strip()
    return normalized_event_name, normalized_event_detail, title


def _normalize_reporting_period(
    db: Session,
    reporting_period: str | None,
    allow_inactive_selected: bool = False,
) -> str:
    normalized_reporting_period = (reporting_period or "").strip()
    if not normalized_reporting_period:
        raise HTTPException(status_code=400, detail="Reporting period is required")

    active_periods = (
        db.query(ReportingPeriod)
        .filter(ReportingPeriod.is_active.is_(True))
        .all()
    )
    period_config = next((item for item in active_periods if item.code == normalized_reporting_period), None)
    if active_periods and not period_config and allow_inactive_selected:
        period_config = (
            db.query(ReportingPeriod)
            .filter(ReportingPeriod.code == normalized_reporting_period)
            .first()
        )
    if active_periods and not period_config:
        raise HTTPException(status_code=400, detail="Selected reporting period is not configured")

    return normalized_reporting_period


def _serialize(update: ProgramUpdate, request: Request) -> ProgramImpactUpdateRead:
    return ProgramImpactUpdateRead(
        id=update.id,
        university_id=update.university_id,
        university_name=update.university.name if update.university else None,
        program_id=update.program_id,
        program_name=update.program.name if update.program else None,
        title=update.title,
        event_name=update.event_name or update.title,
        event_detail=update.event_detail,
        reporting_period=update.reporting_period,
        reporting_date=update.reporting_date,
        summary=update.summary,
        outcomes=update.outcomes,
        challenges=update.challenges,
        next_steps=update.next_steps,
        beneficiaries_reached=update.beneficiaries_reached,
        volunteers_involved=update.volunteers_involved,
        funds_used=update.funds_used,
        attachments=_attachment_response_rows(update, request),
        submitted_by=update.submitted_by,
        created_at=update.created_at,
        updated_at=update.updated_at,
    )


def _build_updates_query(
    db: Session,
    scoped_university_id: int | None,
    program_id: int | None = None,
    reporting_period: str | None = None,
):
    query = (
        db.query(ProgramUpdate)
        .options(
            selectinload(ProgramUpdate.program),
            selectinload(ProgramUpdate.university).selectinload(University.conference),
            selectinload(ProgramUpdate.submitter),
        )
        .order_by(ProgramUpdate.reporting_date.desc(), ProgramUpdate.created_at.desc())
    )
    if scoped_university_id:
        query = query.filter(ProgramUpdate.university_id == scoped_university_id)
    if program_id:
        query = query.filter(ProgramUpdate.program_id == program_id)
    if reporting_period:
        query = query.filter(ProgramUpdate.reporting_period == reporting_period)
    return query


def _get_update_with_relationships(db: Session, update_id: int) -> ProgramUpdate | None:
    return (
        db.query(ProgramUpdate)
        .options(
            selectinload(ProgramUpdate.program),
            selectinload(ProgramUpdate.university).selectinload(University.conference),
            selectinload(ProgramUpdate.submitter),
        )
        .filter(ProgramUpdate.id == update_id)
        .first()
    )


def _refresh_program_reporting(db: Session, program_id: int | None) -> None:
    if not program_id:
        return

    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        return

    total_reached = (
        db.query(func.coalesce(func.sum(ProgramUpdate.beneficiaries_reached), 0))
        .filter(ProgramUpdate.program_id == program_id)
        .scalar()
    ) or 0
    latest_update = (
        db.query(ProgramUpdate)
        .filter(ProgramUpdate.program_id == program_id)
        .order_by(ProgramUpdate.updated_at.desc(), ProgramUpdate.created_at.desc())
        .first()
    )

    program.beneficiaries_served = int(total_reached)
    program.last_update_at = (
        (latest_update.updated_at or latest_update.created_at)
        if latest_update
        else None
    )


def _condense_text(value: str | None, limit: int = 140) -> str | None:
    normalized = " ".join((value or "").split())
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


@router.get("", response_model=list[ProgramImpactUpdateRead])
def list_updates(
    university_id: int | None = None,
    program_id: int | None = None,
    reporting_period: str | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    query = _build_updates_query(db, scoped_university_id, program_id=program_id, reporting_period=reporting_period)
    return [_serialize(item, request) for item in query.all()]


@router.get("/condensed", response_model=list[CondensedMissionReportRead])
def list_condensed_updates(
    university_id: int | None = None,
    reporting_period: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(GENERAL_USER_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    updates = _build_updates_query(db, scoped_university_id, reporting_period=reporting_period).all()
    period_labels = {
        item.code: item.label
        for item in db.query(ReportingPeriod).order_by(ReportingPeriod.sort_order.asc(), ReportingPeriod.code.asc()).all()
    }

    grouped: dict[tuple[str, str], dict] = {}
    for update in updates:
        key = (update.reporting_period, update.event_name or update.title or "Unspecified event")
        current = grouped.setdefault(
            key,
            {
                "reporting_period": update.reporting_period,
                "reporting_period_label": period_labels.get(update.reporting_period, update.reporting_period),
                "event_name": update.event_name or update.title or "Unspecified event",
                "update_count": 0,
                "university_names": set(),
                "total_beneficiaries_reached": 0,
                "total_volunteers_involved": 0,
                "total_funds_used": 0.0,
                "latest_update_at": None,
                "highlights": [],
            },
        )
        current["update_count"] += 1
        if update.university and update.university.name:
            current["university_names"].add(update.university.name)
        current["total_beneficiaries_reached"] += int(update.beneficiaries_reached or 0)
        current["total_volunteers_involved"] += int(update.volunteers_involved or 0)
        current["total_funds_used"] += float(update.funds_used or 0)

        timestamp = update.updated_at or update.created_at
        if current["latest_update_at"] is None or (timestamp and timestamp > current["latest_update_at"]):
            current["latest_update_at"] = timestamp

        highlight = _condense_text(update.summary)
        if highlight:
            prefix = update.university.name if update.university and update.university.name else "PCM"
            current["highlights"].append((timestamp or datetime.min, f"{prefix}: {highlight}"))

    results = []
    for item in grouped.values():
        sorted_highlights = [
            text for _, text in sorted(item["highlights"], key=lambda row: row[0], reverse=True)[:3]
        ]
        results.append(
            CondensedMissionReportRead(
                reporting_period=item["reporting_period"],
                reporting_period_label=item["reporting_period_label"],
                event_name=item["event_name"],
                update_count=item["update_count"],
                university_count=len(item["university_names"]),
                total_beneficiaries_reached=item["total_beneficiaries_reached"],
                total_volunteers_involved=item["total_volunteers_involved"],
                total_funds_used=round(item["total_funds_used"], 2),
                latest_update_at=item["latest_update_at"],
                highlights=sorted_highlights,
            )
        )

    return sorted(
        results,
        key=lambda item: (
            item.latest_update_at or datetime.min,
            item.reporting_period,
            item.event_name,
        ),
        reverse=True,
    )


@router.get("/report-pack")
def download_report_pack(
    university_id: int | None = None,
    program_id: int | None = None,
    reporting_period: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    updates = _build_updates_query(
        db,
        scoped_university_id,
        program_id=program_id,
        reporting_period=reporting_period,
    ).all()
    if not updates:
        raise HTTPException(status_code=404, detail="No updates found for the selected filters")

    zip_bytes = build_program_update_report_pack(updates)
    scope_label = "all-universities"
    if scoped_university_id and updates[0].university:
        scope_label = updates[0].university.short_code or updates[0].university.name.lower().replace(" ", "-")
    period_label = reporting_period or "all-periods"
    headers = {
        "Content-Disposition": f'attachment; filename="impact-report-pack_{scope_label}_{period_label}.zip"'
    }
    return StreamingResponse(BytesIO(zip_bytes), media_type="application/zip", headers=headers)


@router.get("/consolidated-report-pdf")
def download_consolidated_report_pdf(
    university_id: int | None = None,
    program_id: int | None = None,
    reporting_period: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    updates = _build_updates_query(
        db,
        scoped_university_id,
        program_id=program_id,
        reporting_period=reporting_period,
    ).all()
    if not updates:
        raise HTTPException(status_code=404, detail="No updates found for the selected filters")

    pdf_bytes = build_consolidated_program_update_pdf(updates)
    scope_label = "all-campuses"
    if scoped_university_id and updates[0].university:
        scope_label = updates[0].university.short_code or updates[0].university.name.lower().replace(" ", "-")
    period_label = reporting_period or "all-periods"
    headers = {
        "Content-Disposition": f'attachment; filename="impact-report-consolidated_{scope_label}_{period_label}.pdf"'
    }
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/{update_id}/report-pdf")
def download_single_report_pdf(
    update_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    update = _get_update_with_relationships(db, update_id)
    if not update:
        raise HTTPException(status_code=404, detail="Program update not found")
    resolve_university_scope(user, update.university_id)

    pdf_bytes = build_program_update_pdf(update)
    file_label = (update.event_detail or update.event_name or update.title or f"update_{update.id}").strip().lower()
    safe_label = "".join(char if char.isalnum() else "_" for char in file_label).strip("_") or f"update_{update.id}"
    filename_prefix = "meeting-minutes" if _is_meeting_event_name(update.event_name or update.title) else "impact-report"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename_prefix}_{safe_label}_{update.id}.pdf"'
    }
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.post("", response_model=ProgramImpactUpdateRead)
async def create_update(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    payload, attachments, meeting_minutes_attachments, _, meeting_minutes_metadata = await _parse_payload_from_request(request, patch=False)
    scoped_university_id = resolve_university_scope(user, payload.university_id)
    program = None
    if payload.program_id is not None:
        program = db.query(Program).filter(Program.id == payload.program_id).first()
        if not program or program.university_id != scoped_university_id:
            raise HTTPException(status_code=400, detail="Ministry program does not belong to this university")

    event_name, event_detail, title = _normalize_event_fields(db, payload.event_name, payload.event_detail, payload.title)
    _require_meeting_minutes(event_name, bool(meeting_minutes_attachments))
    payload_data = payload.model_dump(exclude={"university_id", "event_name", "event_detail", "title"})
    payload_data["reporting_period"] = _normalize_reporting_period(db, payload.reporting_period)
    payload_data["reporting_date"] = _normalize_reporting_date(payload.reporting_date)

    saved_attachments = []
    if attachments:
        saved_attachments.extend(await _save_attachments(attachments))
    if meeting_minutes_attachments:
        saved_attachments.extend(await _save_attachments(meeting_minutes_attachments, metadata=meeting_minutes_metadata))

    update = ProgramUpdate(
        **payload_data,
        university_id=scoped_university_id,
        title=title,
        event_name=event_name,
        event_detail=event_detail,
        attachments_json=json.dumps(saved_attachments) if saved_attachments else None,
        submitted_by=user.id,
    )
    db.add(update)
    db.flush()
    _refresh_program_reporting(db, update.program_id)
    db.commit()
    db.refresh(update)
    log_action(db, user.id, "create", "program_update", str(update.id), {"program_id": update.program_id})
    return _serialize(update, request)


@router.patch("/{update_id}", response_model=ProgramImpactUpdateRead)
async def update_program_update(
    update_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    payload, attachments, meeting_minutes_attachments, existing_attachments, meeting_minutes_metadata = await _parse_payload_from_request(request, patch=True)
    update = db.query(ProgramUpdate).filter(ProgramUpdate.id == update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Program update not found")
    previous_program_id = update.program_id

    target_university_id = payload.university_id or update.university_id
    scoped_university_id = resolve_university_scope(user, target_university_id)

    updates = payload.model_dump(exclude_unset=True)
    target_program_id = updates["program_id"] if "program_id" in updates else update.program_id
    program = None
    if target_program_id is not None:
        program = db.query(Program).filter(Program.id == target_program_id).first()
        if not program or program.university_id != scoped_university_id:
            raise HTTPException(status_code=400, detail="Ministry program does not belong to this university")
    allow_inactive_selected = "event_name" not in updates or updates.get("event_name") == (update.event_name or update.title)
    event_name, event_detail, title = _normalize_event_fields(
        db,
        updates.get("event_name", update.event_name or update.title),
        updates.get("event_detail", update.event_detail),
        updates.get("title", update.title),
        allow_inactive_selected=allow_inactive_selected,
    )
    updates["title"] = title
    updates["event_name"] = event_name
    updates["event_detail"] = event_detail
    allow_inactive_reporting_period = "reporting_period" not in updates or updates.get("reporting_period") == update.reporting_period
    updates["reporting_period"] = _normalize_reporting_period(
        db,
        updates.get("reporting_period", update.reporting_period),
        allow_inactive_selected=allow_inactive_reporting_period,
    )
    if "reporting_date" in updates:
        updates["reporting_date"] = _normalize_reporting_date(updates.get("reporting_date"))

    current_attachments = _load_attachments(update)
    if existing_attachments is None:
        kept_attachments = current_attachments
        removed_attachments = []
    else:
        requested_stored_names = {
            item.get("stored_name") or item.get("path")
            for item in existing_attachments
            if isinstance(item, dict)
        }
        kept_attachments = [
            item for item in current_attachments if (item.get("stored_name") or item.get("path")) in requested_stored_names
        ]
        removed_attachments = [
            item for item in current_attachments if (item.get("stored_name") or item.get("path")) not in requested_stored_names
        ]

    kept_attachments = _apply_meeting_minutes_metadata(kept_attachments, meeting_minutes_metadata)
    _delete_attachment_files(removed_attachments)

    if attachments:
        kept_attachments.extend(await _save_attachments(attachments))
    if meeting_minutes_attachments:
        kept_attachments.extend(await _save_attachments(meeting_minutes_attachments, metadata=meeting_minutes_metadata))
    _require_meeting_minutes(
        event_name,
        any(item.get("category") == "minutes" for item in kept_attachments),
    )
    updates["attachments_json"] = json.dumps(kept_attachments) if kept_attachments else None

    for key, value in updates.items():
        setattr(update, key, value)
    db.flush()
    _refresh_program_reporting(db, previous_program_id)
    if update.program_id != previous_program_id:
        _refresh_program_reporting(db, update.program_id)
    db.commit()
    db.refresh(update)
    log_action(db, user.id, "update", "program_update", str(update.id), {"program_id": update.program_id})
    return _serialize(update, request)


@router.delete("/{update_id}")
def delete_program_update(
    update_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    update = db.query(ProgramUpdate).filter(ProgramUpdate.id == update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Program update not found")
    resolve_university_scope(user, update.university_id)
    previous_program_id = update.program_id

    _delete_attachment_files(_load_attachments(update))
    db.delete(update)
    db.flush()
    _refresh_program_reporting(db, previous_program_id)
    db.commit()
    log_action(db, user.id, "delete", "program_update", str(update_id), None)
    return {"status": "deleted"}
