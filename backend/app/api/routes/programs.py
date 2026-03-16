from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import Program, University
from ...schemas import ProgramCreate, ProgramRead, ProgramUpdatePayload
from ...services.audit_log import log_action
from ...services.rbac import get_user_roles
from ..deps import (
    PROGRAM_ROLES,
    apply_university_scope_filter,
    require_role,
    resolve_university_scope,
    resolve_visible_university_ids,
)

router = APIRouter(prefix="/programs", tags=["programs"])
NETWORK_PROGRAM_LABEL = "All universities and campuses"
PROGRAM_AUDIENCES = {"Students", "Alumni", "Students and Alumni"}
ALUMNI_ALLOWED_AUDIENCES = {"alumni", "students and alumni"}


def _normalize_audience(value: str | None) -> str:
    normalized = (value or "Students").strip()
    if not normalized:
        return "Students"
    if normalized not in PROGRAM_AUDIENCES:
        raise HTTPException(status_code=400, detail="Invalid program audience")
    return normalized


def _audience_supports_alumni(value: str | None) -> bool:
    return _normalize_audience(value).strip().lower() in ALUMNI_ALLOWED_AUDIENCES


def _validate_program_window(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="Program end date must be on or after the start date")


def _calculate_duration_weeks(start_date: date | None, end_date: date | None) -> float | None:
    if start_date is None or end_date is None:
        return None
    _validate_program_window(start_date, end_date)
    duration_days = (end_date - start_date).days + 1
    return round(duration_days / 7, 1)


def _resolve_program_scope(db: Session, user, requested_university_id: int | None) -> int | None:
    if requested_university_id is None:
        if user.university_id or user.union_id:
            raise HTTPException(status_code=403, detail="Only global-access users can manage network-wide programs")
        return None
    return resolve_university_scope(db, user, requested_university_id)


def _ensure_program_mutation_access(db: Session, user, program: Program) -> None:
    if program.university_id is None:
        if user.university_id or user.union_id:
            raise HTTPException(status_code=403, detail="Only global-access users can modify network-wide programs")
        return
    resolve_university_scope(db, user, program.university_id)


def _enforce_program_role_rules(db: Session, user, audience: str | None) -> None:
    user_roles = set(get_user_roles(db, user))
    if "alumni_admin" in user_roles and not _audience_supports_alumni(audience):
        raise HTTPException(status_code=403, detail="Alumni admins can only manage alumni-focused programs")


def _is_reported_completed_program(program: Program) -> bool:
    if not program.updates:
        return False
    completion_date = program.end_date or program.start_date
    if completion_date is None:
        return False
    return completion_date < date.today()


def _serialize(program: Program) -> ProgramRead:
    return ProgramRead(
        id=program.id,
        university_id=program.university_id,
        university_name=program.university.name if program.university else NETWORK_PROGRAM_LABEL,
        name=program.name,
        category=program.category,
        status=program.status,
        description=program.description,
        audience=_normalize_audience(program.audience),
        manager_name=program.manager_name,
        target_beneficiaries=program.target_beneficiaries,
        beneficiaries_served=program.beneficiaries_served,
        annual_budget=program.annual_budget,
        duration_weeks=program.duration_weeks,
        level=program.level,
        start_date=program.start_date,
        end_date=program.end_date,
        last_update_at=program.last_update_at,
        update_count=len(program.updates),
    )


@router.get("", response_model=list[ProgramRead])
def list_programs(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    scoped_university_ids = resolve_visible_university_ids(
        db,
        user,
        requested_university_id=university_id,
        requested_conference_id=conference_id,
        requested_union_id=union_id,
    )
    query = db.query(Program).order_by(Program.name.asc())
    query = apply_university_scope_filter(query, Program, scoped_university_ids, include_network_records=True)
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=ProgramRead)
def create_program(
    payload: ProgramCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    scoped_university_id = _resolve_program_scope(db, user, payload.university_id)
    audience = _normalize_audience(payload.audience)
    _enforce_program_role_rules(db, user, audience)
    _validate_program_window(payload.start_date, payload.end_date)
    if scoped_university_id is not None:
        university = db.query(University).filter(University.id == scoped_university_id).first()
        if not university:
            raise HTTPException(status_code=404, detail="University not found")

    payload_data = payload.model_dump(exclude={"university_id", "audience"})
    if payload.start_date and payload.end_date:
        payload_data["duration_weeks"] = _calculate_duration_weeks(payload.start_date, payload.end_date)

    program = Program(
        **payload_data,
        university_id=scoped_university_id,
        audience=audience,
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    log_action(db, user.id, "create", "program", str(program.id), {"university_id": program.university_id})
    return _serialize(program)


@router.patch("/{program_id}", response_model=ProgramRead)
def update_program(
    program_id: int,
    payload: ProgramUpdatePayload,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    _ensure_program_mutation_access(db, user, program)

    updates = payload.model_dump(exclude_unset=True)
    target_audience = _normalize_audience(updates["audience"]) if "audience" in updates else _normalize_audience(program.audience)
    _enforce_program_role_rules(db, user, target_audience)
    merged_start_date = updates["start_date"] if "start_date" in updates else program.start_date
    merged_end_date = updates["end_date"] if "end_date" in updates else program.end_date
    _validate_program_window(merged_start_date, merged_end_date)
    if "university_id" in updates:
        updates["university_id"] = _resolve_program_scope(db, user, updates.get("university_id"))
        if updates["university_id"] is not None:
            university = db.query(University).filter(University.id == updates["university_id"]).first()
            if not university:
                raise HTTPException(status_code=404, detail="University not found")
    if "audience" in updates:
        updates["audience"] = target_audience
    if "start_date" in updates or "end_date" in updates or ("duration_weeks" in updates and merged_start_date and merged_end_date):
        updates["duration_weeks"] = _calculate_duration_weeks(merged_start_date, merged_end_date)

    for key, value in updates.items():
        setattr(program, key, value)
    db.commit()
    db.refresh(program)
    log_action(db, user.id, "update", "program", str(program.id), {"university_id": program.university_id})
    return _serialize(program)


@router.delete("/{program_id}")
def delete_program(
    program_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(PROGRAM_ROLES)),
):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    _ensure_program_mutation_access(db, user, program)
    if _is_reported_completed_program(program):
        raise HTTPException(
            status_code=409,
            detail="Programs that have already occurred and been reported on cannot be deleted",
        )

    db.delete(program)
    db.commit()
    log_action(db, user.id, "delete", "program", str(program_id), {"university_id": program.university_id})
    return {"status": "deleted"}
