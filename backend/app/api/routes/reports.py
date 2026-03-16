import json
from datetime import datetime, date
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models import ParsedReportRow, UploadedReport
from ...schemas import UploadReportResponse, UploadedReportRead, ParsedRowRead
from ..deps import apply_university_scope_filter, require_role, resolve_university_scope, resolve_visible_university_ids
from ...core.config import settings

router = APIRouter(prefix="/reports", tags=["reports"])


def _save_file(file: UploadFile) -> str:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    dest = Path(settings.upload_dir) / filename
    with dest.open("wb") as f:
        f.write(file.file.read())
    return str(dest)


# upload endpoint removed; form-based submission is the primary workflow


@router.post("/submit-form", response_model=UploadReportResponse)
def submit_form_report(
    period_start: date = Form(...),
    period_end: date = Form(...),
    students_count: int = Form(...),
    programs_count: int = Form(...),
    programs_json: str = Form(...),
    university_id: int | None = Form(None),
    report_type: str | None = Form("semester_form"),
    images: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin", "student_admin", "secretary"])),
):
    # Parse program entries from JSON
    try:
        programs = json.loads(programs_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid programs JSON")

    scoped_university_id = resolve_university_scope(db, user, university_id)

    # Save optional attachment (cover image, etc.)
    stored_images: list[str] = []
    for img in images:
        ext = img.filename.split(".")[-1].lower()
        if ext not in settings.allowed_upload_extensions.split(","):
            raise HTTPException(status_code=400, detail="Invalid file type")
        stored_images.append(_save_file(img))

    report = UploadedReport(
        template_id=None,
        university_id=scoped_university_id,
        period_start=period_start,
        period_end=period_end,
        report_type=report_type,
        original_filename="form_submission",
        stored_path="form_submission",
        uploaded_by=user.id,
        status="processed",
        processed_at=datetime.utcnow(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Store summary row
    summary = {
        "students_count": students_count,
        "programs_count": programs_count,
        "period_start": str(period_start),
        "period_end": str(period_end),
    }
    db.add(ParsedReportRow(
        uploaded_report_id=report.id,
        row_index=0,
        data_json=json.dumps(summary),
        is_valid="true"
    ))

    # Store program rows
    for idx, program in enumerate(programs, start=1):
        image_indices = program.get("image_indices", [])
        program["images"] = [stored_images[i] for i in image_indices if i < len(stored_images)]
        program.pop("image_indices", None)
        db.add(ParsedReportRow(
            uploaded_report_id=report.id,
            row_index=idx,
            data_json=json.dumps(program),
            is_valid="true"
        ))
    db.commit()
    return UploadReportResponse(id=report.id, status=report.status, original_filename=report.original_filename)


@router.get("", response_model=list[UploadedReportRead])
def list_reports(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin", "student_admin", "secretary"])),
):
    scoped_university_ids = resolve_visible_university_ids(
        db,
        user,
        requested_university_id=university_id,
        requested_conference_id=conference_id,
        requested_union_id=union_id,
    )
    query = db.query(UploadedReport).order_by(UploadedReport.uploaded_at.desc(), UploadedReport.id.desc())
    query = apply_university_scope_filter(query, UploadedReport, scoped_university_ids)
    return query.all()


@router.get("/{report_id}/rows", response_model=list[ParsedRowRead])
def report_rows(report_id: int, db: Session = Depends(get_db), user=Depends(require_role(["super_admin", "student_admin", "secretary"]))):
    report = db.query(UploadedReport).filter(UploadedReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    resolve_university_scope(db, user, report.university_id)
    rows = []
    for row in report.rows:
        rows.append(ParsedRowRead(
            id=row.id,
            row_index=row.row_index,
            data=json.loads(row.data_json),
            is_valid=row.is_valid == "true",
            validation_errors=json.loads(row.validation_errors_json) if row.validation_errors_json else None,
        ))
    return rows
