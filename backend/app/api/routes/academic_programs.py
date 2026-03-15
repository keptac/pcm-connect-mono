from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import AcademicProgram
from ...schemas import AcademicProgramRead
from ..deps import CHAPTER_ROLES, require_role, resolve_university_scope

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
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    query = db.query(AcademicProgram).order_by(AcademicProgram.name.asc())
    if scoped_university_id:
        query = query.filter(AcademicProgram.university_id == scoped_university_id)
    if active_only:
        query = query.filter(AcademicProgram.is_active.is_(True))
    return [_serialize(item) for item in query.all()]
