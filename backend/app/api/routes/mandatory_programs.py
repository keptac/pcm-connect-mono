from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import MandatoryProgram
from ...schemas import MandatoryProgramCreate, MandatoryProgramRead, MandatoryProgramUpdate
from ...services.audit_log import log_action
from ..deps import require_non_service_recovery, require_role

router = APIRouter(prefix="/mandatory-programs", tags=["mandatory-programs"])


def _serialize(item: MandatoryProgram) -> MandatoryProgramRead:
    return MandatoryProgramRead(
        id=item.id,
        name=item.name,
        program_type=item.program_type or "event",
        allow_other_detail=item.allow_other_detail,
        is_active=item.is_active,
        sort_order=item.sort_order or 0,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[MandatoryProgramRead])
def list_mandatory_programs(
    program_type: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_non_service_recovery),
):
    query = db.query(MandatoryProgram).order_by(MandatoryProgram.sort_order.asc(), MandatoryProgram.name.asc())
    if program_type:
        query = query.filter(MandatoryProgram.program_type == program_type)
    if not include_inactive:
        query = query.filter(MandatoryProgram.is_active.is_(True))
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=MandatoryProgramRead)
def create_mandatory_program(
    payload: MandatoryProgramCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    existing = db.query(MandatoryProgram).filter(MandatoryProgram.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mandatory program already exists")

    item = MandatoryProgram(
        name=payload.name.strip(),
        program_type=(payload.program_type or "event").strip().lower(),
        allow_other_detail=payload.allow_other_detail,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(db, user.id, "create", "mandatory_program", str(item.id), {"name": item.name})
    return _serialize(item)


@router.patch("/{item_id}", response_model=MandatoryProgramRead)
def update_mandatory_program(
    item_id: int,
    payload: MandatoryProgramUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    item = db.query(MandatoryProgram).filter(MandatoryProgram.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Mandatory program not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        normalized_name = updates["name"].strip()
        duplicate = (
            db.query(MandatoryProgram)
            .filter(MandatoryProgram.name == normalized_name, MandatoryProgram.id != item_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="Mandatory program already exists")
        updates["name"] = normalized_name
    if "program_type" in updates and updates["program_type"]:
        updates["program_type"] = updates["program_type"].strip().lower()

    for key, value in updates.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    log_action(db, user.id, "update", "mandatory_program", str(item.id), {"name": item.name})
    return _serialize(item)


@router.delete("/{item_id}")
def delete_mandatory_program(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["super_admin"])),
):
    item = db.query(MandatoryProgram).filter(MandatoryProgram.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Mandatory program not found")

    db.delete(item)
    db.commit()
    log_action(db, user.id, "delete", "mandatory_program", str(item_id), {"name": item.name})
    return {"status": "deleted"}
