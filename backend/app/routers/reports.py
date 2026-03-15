import csv
import json
from io import StringIO
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
from sqlmodel import Session, select
from ..db import get_session
from ..models import ReportUpload, ReportRow, User
from ..schemas import ReportUploadRead, ReportRowRead, ReportAnalysis
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/template")
def download_template():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value", "unit", "category", "notes"])
    writer.writerow(["bible_studies", "12", "count", "evangelism", ""])
    writer.writerow(["attendance", "240", "count", "worship", ""])
    content = output.getvalue()
    headers = {"Content-Disposition": "attachment; filename=pcm_report_template.csv"}
    return Response(content=content, media_type="text/csv", headers=headers)


@router.post("/upload", response_model=ReportUploadRead)
def upload_report(
    report_period: str | None = Form(None),
    university_id: int | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current: User = Depends(require_role("admin", "student_admin")),
):
    if current.role != "admin" and not current.university_id:
        raise HTTPException(status_code=400, detail="University required")
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    resolved_university_id = current.university_id if current.role != "admin" else university_id
    upload = ReportUpload(
        university_id=resolved_university_id or 0,
        uploaded_by=current.id,
        original_filename=file.filename or "report.csv",
        report_period=report_period,
    )
    if upload.university_id == 0:
        raise HTTPException(status_code=400, detail="Admin must select a university context")
    session.add(upload)
    session.commit()
    session.refresh(upload)

    for row in reader:
        value = None
        if row.get("value"):
            try:
                value = float(row.get("value"))
            except ValueError:
                value = None
        report_row = ReportRow(
            report_id=upload.id,
            metric=row.get("metric"),
            value=value,
            unit=row.get("unit"),
            category=row.get("category"),
            notes=row.get("notes"),
            row_data=json.dumps(row),
        )
        session.add(report_row)
    session.commit()
    return upload


@router.get("", response_model=list[ReportUploadRead])
def list_reports(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if current.role == "admin":
        return session.exec(select(ReportUpload)).all()
    if current.university_id:
        return session.exec(select(ReportUpload).where(ReportUpload.university_id == current.university_id)).all()
    return []


@router.get("/{report_id}/rows", response_model=list[ReportRowRead])
def get_report_rows(
    report_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    report = session.get(ReportUpload, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current.role != "admin" and report.university_id != current.university_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return session.exec(select(ReportRow).where(ReportRow.report_id == report_id)).all()


@router.get("/{report_id}/analysis", response_model=ReportAnalysis)
def analyze_report(
    report_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    report = session.get(ReportUpload, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current.role != "admin" and report.university_id != current.university_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = session.exec(select(ReportRow).where(ReportRow.report_id == report_id)).all()
    totals = {}
    categories = {}
    metrics = []
    for row in rows:
        if row.metric and row.metric not in metrics:
            metrics.append(row.metric)
        if row.metric and row.value is not None:
            totals[row.metric] = totals.get(row.metric, 0) + row.value
        if row.category:
            categories[row.category] = categories.get(row.category, 0) + 1
    return ReportAnalysis(
        total_rows=len(rows),
        metrics=metrics,
        totals_by_metric=totals,
        categories=categories,
    )
