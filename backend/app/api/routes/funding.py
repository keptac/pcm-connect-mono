from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import FundingRecord, Program
from ...schemas import FundingRecordCreate, FundingRecordPatch, FundingRecordRead
from ...services.audit_log import log_action
from ..deps import FUNDING_ROLES, FUNDING_WRITE_ROLES, require_role, resolve_university_scope

router = APIRouter(prefix="/funding", tags=["funding"])


def _normalize_category(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _legacy_defaults(entry_type: str | None) -> tuple[str, str, str | None]:
    normalized = (entry_type or "").strip().lower()
    if normalized == "expense":
        return "outflow", "Other", "Expense"
    if normalized == "donation":
        return "inflow", "Donation", None
    if normalized == "zunde":
        return "inflow", "Zunde", None
    if normalized == "offering":
        return "inflow", "Offering", None
    if normalized in {"subscription", "subscriptions"}:
        return "inflow", "Subscriptions", None
    if normalized == "grant":
        return "inflow", "Other", "Grant"
    if normalized == "sponsorship":
        return "inflow", "Other", "Sponsorship"
    return "inflow", "Other", "Legacy receipt"


def _entry_type_from_receipt(direction: str, category: str) -> str:
    if direction == "outflow":
        return "expense"
    return category.strip().lower().replace(" ", "_")


def _normalize_receipt_payload(data: dict) -> dict:
    legacy_direction, legacy_category, legacy_detail = _legacy_defaults(data.get("entry_type"))
    direction = (data.get("flow_direction") or legacy_direction or "inflow").strip().lower()
    if direction not in {"inflow", "outflow"}:
        raise HTTPException(status_code=400, detail="Invalid flow direction")

    category = _normalize_category(data.get("receipt_category")) or legacy_category
    detail = _normalize_category(data.get("category_detail")) or legacy_detail
    reporting_window = (data.get("reporting_window") or "monthly").strip().lower()
    if reporting_window not in {"weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="Reporting window must be weekly or monthly")
    if category == "Other" and not detail:
        raise HTTPException(status_code=400, detail="Specify the category detail when category is Other")
    if category != "Other":
        detail = None

    data["flow_direction"] = direction
    data["receipt_category"] = category
    data["category_detail"] = detail
    data["reporting_window"] = reporting_window
    data["entry_type"] = _entry_type_from_receipt(direction, category)
    return data


def _serialize(record: FundingRecord) -> FundingRecordRead:
    flow_direction, receipt_category, category_detail = _legacy_defaults(record.entry_type)
    return FundingRecordRead(
        id=record.id,
        university_id=record.university_id,
        university_name=record.university.name if record.university else "PCM Office / National Office",
        program_id=record.program_id,
        program_name=record.program.name if record.program else None,
        source_name=record.source_name,
        entry_type=record.entry_type,
        flow_direction=record.flow_direction or flow_direction,
        receipt_category=record.receipt_category or receipt_category,
        category_detail=record.category_detail or category_detail,
        reporting_window=record.reporting_window or "monthly",
        amount=record.amount,
        currency=record.currency,
        transaction_date=record.transaction_date,
        channel=record.channel,
        designation=record.designation,
        notes=record.notes,
        recorded_by=record.recorded_by,
        created_at=record.created_at,
    )


@router.get("", response_model=list[FundingRecordRead])
def list_funding(
    university_id: int | None = None,
    flow_direction: str | None = None,
    receipt_category: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(FUNDING_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    query = db.query(FundingRecord).order_by(FundingRecord.transaction_date.desc(), FundingRecord.id.desc())
    if scoped_university_id:
        query = query.filter(FundingRecord.university_id == scoped_university_id)
    if flow_direction:
        query = query.filter(FundingRecord.flow_direction == flow_direction)
    if receipt_category:
        query = query.filter(FundingRecord.receipt_category == receipt_category)
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=FundingRecordRead)
def create_funding_record(
    payload: FundingRecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(FUNDING_WRITE_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, payload.university_id)
    if scoped_university_id is None and payload.program_id:
        raise HTTPException(status_code=400, detail="HQ treasury records cannot be linked to a university program")
    if payload.program_id:
        program = db.query(Program).filter(Program.id == payload.program_id).first()
        if not program or program.university_id != scoped_university_id:
            raise HTTPException(status_code=400, detail="Program does not belong to this university")

    payload_data = _normalize_receipt_payload(payload.model_dump(exclude={"university_id"}))
    record = FundingRecord(
        **payload_data,
        university_id=scoped_university_id,
        recorded_by=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    log_action(db, user.id, "create", "funding_record", str(record.id), {"entry_type": record.entry_type})
    return _serialize(record)


@router.patch("/{record_id}", response_model=FundingRecordRead)
def update_funding_record(
    record_id: int,
    payload: FundingRecordPatch,
    db: Session = Depends(get_db),
    user=Depends(require_role(FUNDING_WRITE_ROLES)),
):
    record = db.query(FundingRecord).filter(FundingRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Funding record not found")

    updated_data = payload.model_dump(exclude_unset=True)
    target_university_id = updated_data["university_id"] if "university_id" in updated_data else record.university_id
    scoped_university_id = resolve_university_scope(user, target_university_id)
    target_program_id = updated_data["program_id"] if "program_id" in updated_data else record.program_id
    if scoped_university_id is None and target_program_id:
        raise HTTPException(status_code=400, detail="HQ treasury records cannot be linked to a university program")
    if target_program_id:
        program = db.query(Program).filter(Program.id == target_program_id).first()
        if not program or program.university_id != scoped_university_id:
            raise HTTPException(status_code=400, detail="Program does not belong to this university")

    merged_data = {
        "source_name": record.source_name,
        "entry_type": record.entry_type,
        "flow_direction": record.flow_direction,
        "receipt_category": record.receipt_category,
        "category_detail": record.category_detail,
        "reporting_window": record.reporting_window,
        "amount": record.amount,
        "currency": record.currency,
        "transaction_date": record.transaction_date,
        "channel": record.channel,
        "designation": record.designation,
        "notes": record.notes,
        "program_id": record.program_id,
        "university_id": record.university_id,
    }
    merged_data.update(updated_data)
    updated_data = _normalize_receipt_payload(merged_data)

    for key, value in updated_data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    log_action(db, user.id, "update", "funding_record", str(record.id), {"entry_type": record.entry_type})
    return _serialize(record)


@router.delete("/{record_id}")
def delete_funding_record(
    record_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(FUNDING_WRITE_ROLES)),
):
    record = db.query(FundingRecord).filter(FundingRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Funding record not found")
    resolve_university_scope(user, record.university_id)

    db.delete(record)
    db.commit()
    log_action(db, user.id, "delete", "funding_record", str(record_id), None)
    return {"status": "deleted"}
