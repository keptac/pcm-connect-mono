from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import AcademicProgram
from ...schemas import AcademicProgramRead
from ..deps import CHAPTER_ROLES, apply_university_scope_filter, require_role, resolve_visible_university_ids

router = APIRouter(prefix="/academic-programs", tags=["academic-programs"])


def _serialize(program: AcademicProgram) -> AcademicProgramRead:
    return AcademicProgramRead(
        id=program.id,
        university_id=program.university_id,
        university_name=program.university.name if program.university else None,
        name=program.name,
        faculty=program.faculty,
        study_area=program.study_area,
        qualification_level=program.qualification_level,
        is_active=program.is_active,
        created_at=program.created_at,
    )


@router.get("", response_model=list[AcademicProgramRead])
def list_academic_programs(
    university_id: int | None = None,
    conference_id: int | None = None,
    union_id: int | None = None,
    active_only: bool = True,
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
    query = db.query(AcademicProgram).order_by(AcademicProgram.name.asc())
    query = apply_university_scope_filter(query, AcademicProgram, scoped_university_ids)
    if active_only:
        query = query.filter(AcademicProgram.is_active.is_(True))
    return [_serialize(item) for item in query.all()]
