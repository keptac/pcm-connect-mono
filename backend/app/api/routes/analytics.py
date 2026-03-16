from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas import (
    DashboardOverview,
    FundingBreakdown,
    GroupedStats,
    ProgramPerformance,
    UniversityPerformance,
)
from ...services.analytics import (
    dashboard_overview,
    funding_breakdown,
    member_breakdown,
    program_performance,
    university_performance,
)
from ..deps import CHAPTER_ROLES, require_role, resolve_visible_university_ids

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=DashboardOverview)
def overview(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
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
    return DashboardOverview(**dashboard_overview(db, scoped_university_ids))


@router.get("/people", response_model=list[GroupedStats])
def people(
    group_by: str = "status",
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
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
    return [GroupedStats(**item) for item in member_breakdown(db, group_by, scoped_university_ids)]


@router.get("/universities", response_model=list[UniversityPerformance])
def universities(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
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
    return [UniversityPerformance(**item) for item in university_performance(db, scoped_university_ids)]


@router.get("/programs", response_model=list[ProgramPerformance])
def programs(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
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
    return [ProgramPerformance(**item) for item in program_performance(db, scoped_university_ids)]


@router.get("/funding", response_model=FundingBreakdown)
def funding(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
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
    return FundingBreakdown(**funding_breakdown(db, scoped_university_ids))
