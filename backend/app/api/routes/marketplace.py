from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import MarketplaceInterest, MarketplaceListing, University
from ...schemas import (
    MarketplaceInterestCreate,
    MarketplaceInterestRead,
    MarketplaceListingCreate,
    MarketplaceListingRead,
    MarketplaceListingUpdate,
)
from ...services.rbac import get_user_roles
from ..deps import GLOBAL_VISIBILITY_ROLES, require_marketplace_access

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

LISTING_TYPES = {"offer", "need"}
LISTING_STATUSES = {"active", "closed"}


def _normalize_listing_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in LISTING_TYPES:
        raise HTTPException(status_code=400, detail="Listing type must be 'offer' or 'need'")
    return normalized


def _normalize_status(value: str | None) -> str:
    normalized = (value or "active").strip().lower()
    if normalized not in LISTING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid listing status")
    return normalized


def _serialize_interest(item: MarketplaceInterest) -> MarketplaceInterestRead:
    responder = item.user
    responder_member = responder.member if responder else None
    responder_university = (responder_member.university if responder_member else None) or (responder.university if responder else None)
    return MarketplaceInterestRead(
        id=item.id,
        listing_id=item.listing_id,
        user_id=item.user_id,
        responder_name=responder.name if responder else None,
        responder_email=(responder_member.email if responder_member and responder_member.email else responder.email if responder else ""),
        responder_member_id=responder_member.member_id if responder_member else None,
        responder_member_status=responder_member.status if responder_member else None,
        responder_university_name=responder_university.name if responder_university else None,
        responder_chat_ready=bool(responder and responder.chat_public_key),
        employment_status=responder_member.employment_status if responder_member else None,
        services_offered=responder_member.services_offered if responder_member else None,
        products_supplied=responder_member.products_supplied if responder_member else None,
        note=item.note,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _serialize(
    item: MarketplaceListing,
    response_count: int = 0,
    user_interest: MarketplaceInterest | None = None,
) -> MarketplaceListingRead:
    owner = item.user
    owner_member = owner.member if owner else None
    owner_university = item.university or (owner_member.university if owner_member else None) or (owner.university if owner else None)
    return MarketplaceListingRead(
        id=item.id,
        user_id=item.user_id,
        university_id=item.university_id,
        university_name=owner_university.name if owner_university else None,
        listing_type=item.listing_type,
        title=item.title,
        description=item.description,
        category=item.category,
        price_text=item.price_text,
        owner_name=owner.name if owner else None,
        owner_email=(owner_member.email if owner_member and owner_member.email else owner.email if owner else ""),
        owner_member_id=owner_member.member_id if owner_member else None,
        owner_member_status=owner_member.status if owner_member else None,
        owner_chat_ready=bool(owner and owner.chat_public_key),
        response_count=response_count,
        interest_registered=user_interest is not None,
        interest_note=user_interest.note if user_interest else None,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _can_manage_listing(db: Session, user, item: MarketplaceListing) -> bool:
    if item.user_id == user.id:
        return True
    return bool(set(get_user_roles(db, user)).intersection(GLOBAL_VISIBILITY_ROLES))


def _has_global_posting_rights(db: Session, user) -> bool:
    return bool(set(get_user_roles(db, user)).intersection(GLOBAL_VISIBILITY_ROLES))


def _resolve_posting_university_id(db: Session, user, requested_university_id: int | None) -> int | None:
    if requested_university_id is None:
        return None
    if not _has_global_posting_rights(db, user):
        raise HTTPException(status_code=403, detail="Only users with global visibility can post on behalf of a university or campus")
    university = db.query(University).filter(University.id == requested_university_id).first()
    if not university:
        raise HTTPException(status_code=400, detail="University not found")
    return university.id


def _get_listing_or_404(db: Session, listing_id: int) -> MarketplaceListing:
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.get("", response_model=list[MarketplaceListingRead])
def list_marketplace_listings(
    include_closed: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    query = db.query(MarketplaceListing).order_by(MarketplaceListing.updated_at.desc(), MarketplaceListing.id.desc())
    if not include_closed:
        query = query.filter(MarketplaceListing.status == "active")
    items = query.all()
    listing_ids = [item.id for item in items]
    response_count_map: dict[int, int] = {}
    interest_map: dict[int, MarketplaceInterest] = {}

    if listing_ids:
        response_counts = (
            db.query(MarketplaceInterest.listing_id, func.count(MarketplaceInterest.id))
            .filter(MarketplaceInterest.listing_id.in_(listing_ids))
            .group_by(MarketplaceInterest.listing_id)
            .all()
        )
        response_count_map = {listing_id: count for listing_id, count in response_counts}

        user_interests = (
            db.query(MarketplaceInterest)
            .filter(
                MarketplaceInterest.listing_id.in_(listing_ids),
                MarketplaceInterest.user_id == user.id,
            )
            .all()
        )
        interest_map = {item.listing_id: item for item in user_interests}

    return [
        _serialize(
            item,
            response_count=response_count_map.get(item.id, 0),
            user_interest=interest_map.get(item.id),
        )
        for item in items
    ]


@router.post("", response_model=MarketplaceListingRead)
def create_marketplace_listing(
    payload: MarketplaceListingCreate,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    listing = MarketplaceListing(
        user_id=user.id,
        university_id=_resolve_posting_university_id(db, user, payload.university_id),
        listing_type=_normalize_listing_type(payload.listing_type),
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=(payload.category or "").strip() or None,
        price_text=(payload.price_text or "").strip() or None,
        status="active",
    )
    if not listing.title or not listing.description:
        raise HTTPException(status_code=400, detail="Title and description are required")

    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _serialize(listing)


@router.get("/{listing_id}/interests", response_model=list[MarketplaceInterestRead])
def list_marketplace_interests(
    listing_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    listing = _get_listing_or_404(db, listing_id)
    if not _can_manage_listing(db, user, listing):
        raise HTTPException(status_code=403, detail="You cannot view responses for this listing")

    interests = (
        db.query(MarketplaceInterest)
        .filter(MarketplaceInterest.listing_id == listing.id)
        .order_by(MarketplaceInterest.created_at.desc(), MarketplaceInterest.id.desc())
        .all()
    )
    return [_serialize_interest(item) for item in interests]


@router.post("/{listing_id}/interest", response_model=MarketplaceInterestRead)
def register_marketplace_interest(
    listing_id: int,
    payload: MarketplaceInterestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    listing = _get_listing_or_404(db, listing_id)
    if listing.user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot register interest in your own listing")
    if listing.status != "active":
        raise HTTPException(status_code=400, detail="You can only register interest in an active listing")

    note = (payload.note or "").strip() or None
    interest = (
        db.query(MarketplaceInterest)
        .filter(
            MarketplaceInterest.listing_id == listing.id,
            MarketplaceInterest.user_id == user.id,
        )
        .first()
    )

    if not interest:
        interest = MarketplaceInterest(
            listing_id=listing.id,
            user_id=user.id,
            note=note,
        )
        db.add(interest)
    else:
        interest.note = note

    db.commit()
    db.refresh(interest)
    return _serialize_interest(interest)


@router.delete("/{listing_id}/interest")
def withdraw_marketplace_interest(
    listing_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    _get_listing_or_404(db, listing_id)
    interest = (
        db.query(MarketplaceInterest)
        .filter(
            MarketplaceInterest.listing_id == listing_id,
            MarketplaceInterest.user_id == user.id,
        )
        .first()
    )
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    db.delete(interest)
    db.commit()
    return {"status": "deleted"}


@router.patch("/{listing_id}", response_model=MarketplaceListingRead)
def update_marketplace_listing(
    listing_id: int,
    payload: MarketplaceListingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    listing = _get_listing_or_404(db, listing_id)
    if not _can_manage_listing(db, user, listing):
        raise HTTPException(status_code=403, detail="You cannot manage this listing")

    updates = payload.model_dump(exclude_unset=True)
    if "university_id" in updates:
        updates["university_id"] = _resolve_posting_university_id(db, user, updates["university_id"])
    if "listing_type" in updates:
        updates["listing_type"] = _normalize_listing_type(updates["listing_type"])
    if "status" in updates:
        updates["status"] = _normalize_status(updates["status"])
    for field in ["title", "description", "category", "price_text"]:
        if field in updates and isinstance(updates[field], str):
            updates[field] = updates[field].strip() or None

    if updates.get("title") is None and "title" in updates:
        raise HTTPException(status_code=400, detail="Title is required")
    if updates.get("description") is None and "description" in updates:
        raise HTTPException(status_code=400, detail="Description is required")

    for key, value in updates.items():
        setattr(listing, key, value)
    db.commit()
    db.refresh(listing)
    return _serialize(listing)


@router.delete("/{listing_id}")
def delete_marketplace_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_marketplace_access),
):
    listing = _get_listing_or_404(db, listing_id)
    if not _can_manage_listing(db, user, listing):
        raise HTTPException(status_code=403, detail="You cannot manage this listing")

    db.delete(listing)
    db.commit()
    return {"status": "deleted"}
