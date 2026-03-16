from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import BroadcastInvite, Program, ProgramBroadcast
from ...schemas import (
    BroadcastInviteRead,
    BroadcastInviteUpdate,
    ProgramBroadcastCreate,
    ProgramBroadcastRead,
    ProgramBroadcastUpdate,
)
from ...services.audit_log import log_action
from ..deps import CHAPTER_ROLES, require_non_service_recovery, require_role, resolve_university_scope, resolve_visible_university_ids

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])


def _validate_broadcast_window(starts_at: datetime | None, ends_at: datetime | None) -> None:
    if starts_at and ends_at and ends_at < starts_at:
        raise HTTPException(status_code=400, detail="Broadcast end must be after start")


def _serialize(
    broadcast: ProgramBroadcast,
    viewer_university_ids: set[int] | None = None,
) -> ProgramBroadcastRead:
    invites = [
        BroadcastInviteRead(
            id=invite.id,
            university_id=invite.university_id,
            university_name=invite.university.name if invite.university else None,
            status=invite.status or "invited",
            note=invite.note,
            responded_at=invite.responded_at,
        )
        for invite in sorted(broadcast.invites, key=lambda item: item.university.name if item.university else "")
    ]

    my_invite_status = None
    if viewer_university_ids:
        if broadcast.university_id in viewer_university_ids:
            my_invite_status = "host"
        else:
            scope_statuses = []
            for invite in invites:
                if invite.university_id in viewer_university_ids:
                    scope_statuses.append(invite.status)
            if scope_statuses:
                unique_statuses = sorted(set(scope_statuses))
                my_invite_status = unique_statuses[0] if len(unique_statuses) == 1 else "mixed"
            if not my_invite_status and (broadcast.visibility or "network") == "network":
                my_invite_status = "open"

    return ProgramBroadcastRead(
        id=broadcast.id,
        university_id=broadcast.university_id,
        university_name=broadcast.university.name if broadcast.university else None,
        program_id=broadcast.program_id,
        program_name=broadcast.program.name if broadcast.program else None,
        title=broadcast.title,
        summary=broadcast.summary,
        venue=broadcast.venue,
        contact_name=broadcast.contact_name,
        contact_email=broadcast.contact_email,
        visibility=broadcast.visibility,
        status=broadcast.status,
        starts_at=broadcast.starts_at,
        ends_at=broadcast.ends_at,
        created_by=broadcast.created_by,
        created_at=broadcast.created_at,
        updated_at=broadcast.updated_at,
        invites=invites,
        my_invite_status=my_invite_status,
    )


def _validate_program_scope(db: Session, program_id: int | None, university_id: int) -> None:
    if not program_id:
        return
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program or program.university_id != university_id:
        raise HTTPException(status_code=400, detail="Program does not belong to this university")


def _replace_invites(db: Session, broadcast: ProgramBroadcast, invited_university_ids: list[int]) -> None:
    clean_ids = sorted({invite_id for invite_id in invited_university_ids if invite_id != broadcast.university_id})
    for invite in list(broadcast.invites):
        db.delete(invite)
    db.flush()
    for university_id in clean_ids:
        db.add(
            BroadcastInvite(
                broadcast_id=broadcast.id,
                university_id=university_id,
                status="invited",
            )
        )


def _is_visible_to_scope(broadcast: ProgramBroadcast, university_ids: set[int]) -> bool:
    if not university_ids:
        return False
    if broadcast.university_id in university_ids:
        return True
    if (broadcast.visibility or "network") == "network":
        return True
    return any(invite.university_id in university_ids for invite in broadcast.invites)


@router.get("", response_model=list[ProgramBroadcastRead])
def list_broadcasts(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
    program_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_non_service_recovery),
):
    viewer_university_ids = resolve_visible_university_ids(
        db,
        user,
        requested_university_id=university_id,
        requested_conference_id=conference_id,
        requested_union_id=union_id,
    )
    query = db.query(ProgramBroadcast).order_by(ProgramBroadcast.created_at.desc(), ProgramBroadcast.id.desc())
    if program_id:
        query = query.filter(ProgramBroadcast.program_id == program_id)

    items = query.all()
    if viewer_university_ids is not None:
        items = [item for item in items if _is_visible_to_scope(item, viewer_university_ids)]
    return [_serialize(item, viewer_university_ids) for item in items]


@router.post("", response_model=ProgramBroadcastRead)
def create_broadcast(
    payload: ProgramBroadcastCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_id = resolve_university_scope(db, user, payload.university_id)
    _validate_program_scope(db, payload.program_id, scoped_university_id)
    _validate_broadcast_window(payload.starts_at, payload.ends_at)

    if (payload.visibility or "network") == "targeted" and not payload.invited_university_ids:
        raise HTTPException(status_code=400, detail="Targeted broadcasts need invited universities")

    broadcast = ProgramBroadcast(
        **payload.model_dump(exclude={"university_id", "invited_university_ids"}),
        university_id=scoped_university_id,
        created_by=user.id,
    )
    db.add(broadcast)
    db.flush()
    _replace_invites(db, broadcast, payload.invited_university_ids)
    db.commit()
    db.refresh(broadcast)
    log_action(db, user.id, "create", "broadcast", str(broadcast.id), {"title": broadcast.title})
    return _serialize(broadcast, {scoped_university_id})


@router.patch("/{broadcast_id}", response_model=ProgramBroadcastRead)
def update_broadcast(
    broadcast_id: int,
    payload: ProgramBroadcastUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    broadcast = db.query(ProgramBroadcast).filter(ProgramBroadcast.id == broadcast_id).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    scoped_university_id = resolve_university_scope(db, user, payload.university_id or broadcast.university_id)
    _validate_program_scope(db, payload.program_id or broadcast.program_id, scoped_university_id)
    _validate_broadcast_window(payload.starts_at or broadcast.starts_at, payload.ends_at or broadcast.ends_at)

    updates = payload.model_dump(exclude_unset=True, exclude={"invited_university_ids"})
    updates["university_id"] = scoped_university_id
    for key, value in updates.items():
        setattr(broadcast, key, value)

    if payload.invited_university_ids is not None:
        if (broadcast.visibility or "network") == "targeted" and not payload.invited_university_ids:
            raise HTTPException(status_code=400, detail="Targeted broadcasts need invited universities")
        _replace_invites(db, broadcast, payload.invited_university_ids)

    db.commit()
    db.refresh(broadcast)
    log_action(db, user.id, "update", "broadcast", str(broadcast.id), {"title": broadcast.title})
    return _serialize(broadcast, {scoped_university_id})


@router.post("/{broadcast_id}/respond", response_model=ProgramBroadcastRead)
def respond_to_broadcast(
    broadcast_id: int,
    payload: BroadcastInviteUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_non_service_recovery),
):
    if not user.university_id:
        raise HTTPException(status_code=400, detail="Only university-scoped users can respond to invitations")

    broadcast = db.query(ProgramBroadcast).filter(ProgramBroadcast.id == broadcast_id).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    if not _is_visible_to_scope(broadcast, {user.university_id}):
        raise HTTPException(status_code=403, detail="Broadcast is not visible to your university")

    invite = (
        db.query(BroadcastInvite)
        .filter(BroadcastInvite.broadcast_id == broadcast.id, BroadcastInvite.university_id == user.university_id)
        .first()
    )
    if not invite:
        invite = BroadcastInvite(
            broadcast_id=broadcast.id,
            university_id=user.university_id,
        )
        db.add(invite)
        db.flush()

    invite.status = payload.status
    invite.note = payload.note
    invite.responded_at = datetime.utcnow()
    db.commit()
    db.refresh(broadcast)
    log_action(db, user.id, "respond", "broadcast", str(broadcast.id), {"status": payload.status})
    return _serialize(broadcast, {user.university_id})


@router.delete("/{broadcast_id}")
def delete_broadcast(
    broadcast_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    broadcast = db.query(ProgramBroadcast).filter(ProgramBroadcast.id == broadcast_id).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    resolve_university_scope(db, user, broadcast.university_id)

    db.delete(broadcast)
    db.commit()
    log_action(db, user.id, "delete", "broadcast", str(broadcast_id), {"title": broadcast.title})
    return {"status": "deleted"}
