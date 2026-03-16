from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import Union
from ...schemas import UnionCreate, UnionRead, UnionUpdate
from ...services.audit_log import log_action
from ..deps import ADMIN_ROLES, GENERAL_NETWORK_ROLES, require_role

router = APIRouter(prefix="/unions", tags=["unions"])


def _serialize(union: Union) -> UnionRead:
    return UnionRead(
        id=union.id,
        name=union.name,
        is_active=union.is_active,
        conference_count=len(union.conferences),
        created_at=union.created_at,
    )


@router.get("", response_model=list[UnionRead])
def list_unions(
    active_only: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_role(GENERAL_NETWORK_ROLES)),
):
    query = db.query(Union).order_by(Union.name.asc())
    if active_only:
        query = query.filter(Union.is_active.is_(True))
    return [_serialize(item) for item in query.all()]


@router.post("", response_model=UnionRead)
def create_union(
    payload: UnionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    if db.query(Union).filter(Union.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Union already exists")

    union = Union(**payload.model_dump())
    db.add(union)
    db.commit()
    db.refresh(union)
    log_action(db, user.id, "create", "union", str(union.id), {"name": union.name})
    return _serialize(union)


@router.patch("/{union_id}", response_model=UnionRead)
def update_union(
    union_id: int,
    payload: UnionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(ADMIN_ROLES)),
):
    union = db.query(Union).filter(Union.id == union_id).first()
    if not union:
        raise HTTPException(status_code=404, detail="Union not found")

    if payload.name and payload.name != union.name:
        if db.query(Union).filter(Union.name == payload.name).first():
            raise HTTPException(status_code=400, detail="Union already exists")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(union, key, value)
    db.commit()
    db.refresh(union)
    log_action(db, user.id, "update", "union", str(union.id), {"name": union.name})
    return _serialize(union)
