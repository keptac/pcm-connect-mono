from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import false

from ...db.session import get_db
from ...models import BroadcastInvite, Conference, Member, University, UploadedReport, User
from ...schemas import UniversityCreate, UniversityRead, UniversityUpdate
from ...services.audit_log import log_action
from ..deps import ADMIN_ROLES, CHAPTER_ROLES, GENERAL_NETWORK_ROLES, require_role, resolve_university_scope, resolve_visible_university_ids

router = APIRouter(prefix="/universities", tags=["universities"])


def _serialize(university: University) -> UniversityRead:
    return UniversityRead(
        id=university.id,
        name=university.name,
        short_code=university.short_code,
        country=university.country,
        city=university.city,
        region=university.region,
        conference_id=university.conference_id,
        union_id=university.conference.union_id if university.conference else None,
        conference_name=university.conference.name if university.conference else None,
        union_name=university.conference.union_name if university.conference else None,
        mission_focus=university.mission_focus,
        contact_name=university.contact_name,
        contact_email=university.contact_email,
        contact_phone=university.contact_phone,
        is_active=university.is_active,
        created_at=university.created_at,
        program_count=len(university.programs),
        member_count=len(university.members),
    )


@router.get("", response_model=list[UniversityRead])
def list_universities(
    conference_id: int | None = None,
    union_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(GENERAL_NETWORK_ROLES)),
):
    scoped_university_ids = resolve_visible_university_ids(
        db,
        user,
        requested_conference_id=conference_id,
        requested_union_id=union_id,
    )
    query = db.query(University).order_by(University.name.asc())
    if scoped_university_ids is not None:
        if scoped_university_ids:
            query = query.filter(University.id.in_(sorted(scoped_university_ids)))
        else:
            query = query.filter(false())
    return [_serialize(item) for item in query.all()]


@router.get("/public", response_model=list[UniversityRead])
def list_public_universities(
    db: Session = Depends(get_db),
):
    query = db.query(University).filter(University.is_active.is_(True)).order_by(University.name.asc())
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=UniversityRead)
def create_university(
    payload: UniversityCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    if db.query(University).filter(University.name == payload.name).first():
        raise HTTPException(status_code=400, detail="University already exists")
    if payload.conference_id is None:
        raise HTTPException(status_code=400, detail="Conference is required")

    if payload.conference_id is not None:
        conference = db.query(Conference).filter(Conference.id == payload.conference_id).first()
        if not conference:
            raise HTTPException(status_code=400, detail="Conference not found")

    university = University(**payload.model_dump())
    db.add(university)
    db.commit()
    db.refresh(university)
    log_action(db, user.id, "create", "university", str(university.id), {"name": university.name})
    return _serialize(university)


@router.patch("/{university_id}", response_model=UniversityRead)
def update_university(
    university_id: int,
    payload: UniversityUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    university = db.query(University).filter(University.id == university_id).first()
    if not university:
        raise HTTPException(status_code=404, detail="University not found")
    resolve_university_scope(db, user, university.id)

    updates = payload.model_dump(exclude_unset=True)
    if "conference_id" in updates:
        if updates["conference_id"] is None:
            raise HTTPException(status_code=400, detail="Conference is required")
        conference = db.query(Conference).filter(Conference.id == updates["conference_id"]).first()
        if not conference:
            raise HTTPException(status_code=400, detail="Conference not found")

    for key, value in updates.items():
        setattr(university, key, value)
    db.commit()
    db.refresh(university)
    log_action(db, user.id, "update", "university", str(university.id), {"name": university.name})
    return _serialize(university)


@router.delete("/{university_id}")
def delete_university(
    university_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    university = db.query(University).filter(University.id == university_id).first()
    if not university:
        raise HTTPException(status_code=404, detail="University not found")

    dependency_counts = {
        "members": db.query(Member).filter(Member.university_id == university_id).count(),
        "users": db.query(User).filter(User.university_id == university_id).count(),
        "reports": db.query(UploadedReport).filter(UploadedReport.university_id == university_id).count(),
        "broadcast invites": db.query(BroadcastInvite).filter(BroadcastInvite.university_id == university_id).count(),
    }
    blocking_dependencies = [f"{label} ({count})" for label, count in dependency_counts.items() if count]
    if blocking_dependencies:
        raise HTTPException(
            status_code=400,
            detail=f"Remove linked records before deleting this university or campus: {', '.join(blocking_dependencies)}",
        )

    university_name = university.name
    db.delete(university)
    db.commit()
    log_action(db, user.id, "delete", "university", str(university_id), {"name": university_name})
    return {"status": "deleted"}
