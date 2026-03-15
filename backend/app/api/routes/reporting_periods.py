from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import ReportingPeriod
from ...schemas import ReportingPeriodCreate, ReportingPeriodRead, ReportingPeriodUpdate
from ...services.audit_log import log_action
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/reporting-periods", tags=["reporting-periods"])


def _serialize(item: ReportingPeriod) -> ReportingPeriodRead:
    return ReportingPeriodRead(
        id=item.id,
        code=item.code,
        label=item.label,
        start_date=item.start_date,
        end_date=item.end_date,
        is_active=item.is_active,
        sort_order=item.sort_order or 0,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _validate_dates(start_date, end_date) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="Reporting period start date must be before the end date")


@router.get("", response_model=list[ReportingPeriodRead])
def list_reporting_periods(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(ReportingPeriod).order_by(ReportingPeriod.sort_order.desc(), ReportingPeriod.start_date.desc(), ReportingPeriod.code.desc())
    if not include_inactive:
        query = query.filter(ReportingPeriod.is_active.is_(True))
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=ReportingPeriodRead)
def create_reporting_period(
    payload: ReportingPeriodCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    normalized_code = payload.code.strip()
    normalized_label = payload.label.strip()
    _validate_dates(payload.start_date, payload.end_date)

    existing = db.query(ReportingPeriod).filter(ReportingPeriod.code == normalized_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Reporting period code already exists")

    item = ReportingPeriod(
        code=normalized_code,
        label=normalized_label or normalized_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(db, user.id, "create", "reporting_period", str(item.id), {"code": item.code})
    return _serialize(item)


@router.patch("/{item_id}", response_model=ReportingPeriodRead)
def update_reporting_period(
    item_id: int,
    payload: ReportingPeriodUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    item = db.query(ReportingPeriod).filter(ReportingPeriod.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Reporting period not found")

    updates = payload.model_dump(exclude_unset=True)
    if "code" in updates and updates["code"] is not None:
        updates["code"] = updates["code"].strip()
        duplicate = db.query(ReportingPeriod).filter(
            ReportingPeriod.code == updates["code"],
            ReportingPeriod.id != item_id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Reporting period code already exists")
    if "label" in updates and updates["label"] is not None:
        updates["label"] = updates["label"].strip()

    start_date = updates.get("start_date", item.start_date)
    end_date = updates.get("end_date", item.end_date)
    _validate_dates(start_date, end_date)

    for key, value in updates.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    log_action(db, user.id, "update", "reporting_period", str(item.id), {"code": item.code})
    return _serialize(item)


@router.delete("/{item_id}")
def delete_reporting_period(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    item = db.query(ReportingPeriod).filter(ReportingPeriod.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Reporting period not found")

    db.delete(item)
    db.commit()
    log_action(db, user.id, "delete", "reporting_period", str(item_id), {"code": item.code})
    return {"status": "deleted"}
