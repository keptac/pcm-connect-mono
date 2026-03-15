import csv
import json
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models import ReportTemplate
from ...schemas import ReportTemplateCreate, ReportTemplateRead
from ..deps import require_role

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[ReportTemplateRead])
def list_templates(db: Session = Depends(get_db), user=Depends(require_role(["super_admin", "student_admin"]))):
    templates = db.query(ReportTemplate).all()
    results = []
    for tpl in templates:
        results.append(ReportTemplateRead(
            id=tpl.id,
            name=tpl.name,
            version=tpl.version,
            columns=json.loads(tpl.columns_json),
            file_format=tpl.file_format,
            created_at=tpl.created_at,
        ))
    return results


@router.post("", response_model=ReportTemplateRead)
def create_template(payload: ReportTemplateCreate, db: Session = Depends(get_db), user=Depends(require_role(["super_admin"]))):
    tpl = ReportTemplate(
        name=payload.name,
        version=payload.version,
        columns_json=json.dumps(payload.columns),
        file_format=payload.file_format,
        created_by=user.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return ReportTemplateRead(
        id=tpl.id,
        name=tpl.name,
        version=tpl.version,
        columns=payload.columns,
        file_format=tpl.file_format,
        created_at=tpl.created_at,
    )


@router.get("/{template_id}/download")
def download_template(template_id: int, db: Session = Depends(get_db), user=Depends(require_role(["super_admin", "student_admin"]))):
    tpl = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    columns = json.loads(tpl.columns_json)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    content = output.getvalue()
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={tpl.name}_{tpl.version}.csv"})
