from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import CampusEvent, Program
from ...schemas import CampusEventCreate, CampusEventRead, CampusEventUpdate
from ...services.audit_log import log_action
from ..deps import CHAPTER_ROLES, apply_university_scope_filter, require_role, resolve_university_scope, resolve_visible_university_ids

router = APIRouter(prefix="/events", tags=["events"])


def _serialize(event: CampusEvent) -> CampusEventRead:
    return CampusEventRead(
        id=event.id,
        university_id=event.university_id,
        university_name=event.university.name if event.university else None,
        program_id=event.program_id,
        program_name=event.program.name if event.program else None,
        title=event.title,
        event_type=event.event_type,
        audience=event.audience,
        status=event.status,
        venue=event.venue,
        description=event.description,
        organizer_name=event.organizer_name,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        created_by=event.created_by,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _validate_event_window(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at < starts_at:
        raise HTTPException(status_code=400, detail="Event end must be after start")


def _validate_program_scope(db: Session, program_id: int | None, university_id: int) -> None:
    if not program_id:
        return
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program or program.university_id != university_id:
        raise HTTPException(status_code=400, detail="Program does not belong to this university")


@router.get("", response_model=list[CampusEventRead])
def list_events(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
    program_id: int | None = None,
    start_from: datetime | None = None,
    end_to: datetime | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_ids = resolve_visible_university_ids(
        db,
        user,
        requested_university_id=university_id,
        requested_conference_id=conference_id,
        requested_union_id=union_id,
    )
    query = db.query(CampusEvent).order_by(CampusEvent.starts_at.asc(), CampusEvent.id.asc())
    query = apply_university_scope_filter(query, CampusEvent, scoped_university_ids)
    if program_id:
        query = query.filter(CampusEvent.program_id == program_id)
    if start_from:
        query = query.filter(CampusEvent.ends_at >= start_from)
    if end_to:
        query = query.filter(CampusEvent.starts_at <= end_to)
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=CampusEventRead)
def create_event(
    payload: CampusEventCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_id = resolve_university_scope(db, user, payload.university_id)
    _validate_event_window(payload.starts_at, payload.ends_at)
    _validate_program_scope(db, payload.program_id, scoped_university_id)

    event = CampusEvent(
        **payload.model_dump(exclude={"university_id"}),
        university_id=scoped_university_id,
        created_by=user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log_action(db, user.id, "create", "campus_event", str(event.id), {"title": event.title})
    return _serialize(event)


@router.patch("/{event_id}", response_model=CampusEventRead)
def update_event(
    event_id: int,
    payload: CampusEventUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    event = db.query(CampusEvent).filter(CampusEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    target_university_id = payload.university_id or event.university_id
    scoped_university_id = resolve_university_scope(db, user, target_university_id)
    target_program_id = payload.program_id if payload.program_id is not None else event.program_id
    starts_at = payload.starts_at or event.starts_at
    ends_at = payload.ends_at or event.ends_at

    _validate_event_window(starts_at, ends_at)
    _validate_program_scope(db, target_program_id, scoped_university_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    log_action(db, user.id, "update", "campus_event", str(event.id), {"title": event.title})
    return _serialize(event)


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    event = db.query(CampusEvent).filter(CampusEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    resolve_university_scope(db, user, event.university_id)

    db.delete(event)
    db.commit()
    log_action(db, user.id, "delete", "campus_event", str(event_id), {"title": event.title})
    return {"status": "deleted"}
