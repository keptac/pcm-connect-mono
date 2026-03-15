from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import Conference
from ...schemas import ConferenceCreate, ConferenceRead, ConferenceUpdate
from ...services.audit_log import log_action
from ..deps import ADMIN_ROLES, CHAPTER_ROLES, require_role

router = APIRouter(prefix="/conferences", tags=["conferences"])


def _serialize(conference: Conference) -> ConferenceRead:
    return ConferenceRead(
        id=conference.id,
        name=conference.name,
        union_name=conference.union_name,
        is_active=conference.is_active,
        campus_count=len(conference.universities),
        created_at=conference.created_at,
    )


@router.get("", response_model=list[ConferenceRead])
def list_conferences(
    active_only: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    query = db.query(Conference).order_by(Conference.name.asc())
    if active_only:
        query = query.filter(Conference.is_active.is_(True))
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=ConferenceRead)
def create_conference(
    payload: ConferenceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    if db.query(Conference).filter(Conference.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Conference already exists")

    conference = Conference(**payload.model_dump())
    db.add(conference)
    db.commit()
    db.refresh(conference)
    log_action(db, user.id, "create", "conference", str(conference.id), {"name": conference.name})
    return _serialize(conference)


@router.patch("/{conference_id}", response_model=ConferenceRead)
def update_conference(
    conference_id: int,
    payload: ConferenceUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    conference = db.query(Conference).filter(Conference.id == conference_id).first()
    if not conference:
        raise HTTPException(status_code=404, detail="Conference not found")

    if payload.name and payload.name != conference.name:
        if db.query(Conference).filter(Conference.name == payload.name).first():
            raise HTTPException(status_code=400, detail="Conference already exists")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(conference, key, value)
    db.commit()
    db.refresh(conference)
    log_action(db, user.id, "update", "conference", str(conference.id), {"name": conference.name})
    return _serialize(conference)
