import csv
from io import StringIO

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import AcademicProgram, Member
from ...schemas import AlumniConnectRead, MemberCreate, MemberRead, MemberSelfProfileUpdate, MemberUpdate
from ...services.audit_log import log_action
from ...services.rbac import get_user_roles
from ..deps import CHAPTER_ROLES, GENERAL_NETWORK_ROLES, get_current_user, require_role, resolve_university_scope

router = APIRouter(prefix="/members", tags=["members"])

ALLOWED_MEMBER_STATUSES = {"Student", "Staff", "Alumni", "Volunteer", "Partner"}
FULL_MEMBER_ACCESS_ROLES = {"super_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director"}


def _member_access_scope(db: Session, user) -> tuple[set[str] | None, set[str] | None]:
    user_roles = set(get_user_roles(db, user))
    if user_roles.intersection(FULL_MEMBER_ACCESS_ROLES):
        return None, None

    visible_statuses: set[str] = set()
    writable_statuses: set[str] = set()

    if "alumni_admin" in user_roles:
        visible_statuses.update({"Alumni", "Student", "Staff"})
        writable_statuses.add("Alumni")
    if "student_admin" in user_roles:
        visible_statuses.add("Student")
        writable_statuses.add("Student")

    return (visible_statuses or None, writable_statuses or None)


def _ensure_member_visible(member_status: str | None, visible_statuses: set[str] | None) -> None:
    if visible_statuses is None:
        return
    if (member_status or "Student") not in visible_statuses:
        raise HTTPException(status_code=403, detail="You do not have access to this member type")


def _normalize_member_status_for_user(
    status: str | None,
    writable_statuses: set[str] | None,
) -> str:
    normalized = _normalize_member_status(status)
    if writable_statuses is None:
        return normalized
    if len(writable_statuses) == 1:
        return next(iter(writable_statuses))
    if normalized not in writable_statuses:
        raise HTTPException(status_code=403, detail="You cannot manage this member type")
    return normalized


def _ensure_member_writable(member_status: str | None, writable_statuses: set[str] | None) -> None:
    if writable_statuses is None:
        return
    if (member_status or "Student") not in writable_statuses:
        raise HTTPException(status_code=403, detail="You cannot modify this member type")


def _serialize(member: Member) -> MemberRead:
    return MemberRead(
        id=str(member.id),
        member_id=member.member_id,
        first_name=member.first_name,
        last_name=member.last_name,
        gender=member.gender,
        dob=member.dob,
        phone=member.phone,
        email=member.email,
        university_id=member.university_id,
        program_of_study_id=member.program_of_study_id,
        program_of_study_name=member.program_of_study.name if member.program_of_study else None,
        start_year=member.start_year,
        expected_graduation_date=member.expected_graduation_date,
        intake=member.intake,
        status=member.status,
        employment_status=member.employment_status,
        employer_name=member.employer_name,
        current_city=member.current_city,
        services_offered=member.services_offered,
        products_supplied=member.products_supplied,
        active=member.active,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _serialize_alumni_connect(member: Member) -> AlumniConnectRead:
    return AlumniConnectRead(
        id=str(member.id),
        member_id=member.member_id,
        first_name=member.first_name,
        last_name=member.last_name,
        university_id=member.university_id,
        university_name=member.university.name if member.university else None,
        program_of_study_name=member.program_of_study.name if member.program_of_study else None,
        expected_graduation_date=member.expected_graduation_date,
        start_year=member.start_year,
        employment_status=member.employment_status,
        employer_name=member.employer_name,
        current_city=member.current_city,
        services_offered=member.services_offered,
        products_supplied=member.products_supplied,
        email=member.email,
    )


def _resolve_program_of_study(
    db: Session,
    university_id: int,
    program_of_study_id: int | None = None,
    program_of_study_name: str | None = None,
) -> int | None:
    if program_of_study_id is not None:
        program = (
            db.query(AcademicProgram)
            .filter(
                AcademicProgram.id == program_of_study_id,
                AcademicProgram.university_id == university_id,
            )
            .first()
        )
        if not program:
            raise HTTPException(status_code=400, detail="Program of study does not belong to this university")
        return program.id

    normalized_name = (program_of_study_name or "").strip()
    if not normalized_name:
        return None

    program = (
        db.query(AcademicProgram)
        .filter(
            AcademicProgram.university_id == university_id,
            func.lower(AcademicProgram.name) == normalized_name.lower(),
        )
        .first()
    )
    if not program:
        raise HTTPException(status_code=400, detail="Program of study was not found for this university")
    return program.id


def _normalize_member_status(status: str | None) -> str:
    normalized = (status or "Student").strip() or "Student"
    if normalized not in ALLOWED_MEMBER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid member type")
    return normalized


def _linked_member_or_404(user, db: Session) -> Member:
    if not user.member_id:
        raise HTTPException(status_code=404, detail="No member profile is linked to this account")

    try:
        member_uuid = UUID(str(user.member_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid linked member profile") from exc

    member = db.query(Member).filter(Member.id == member_uuid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Linked member profile was not found")
    return member


def _member_by_id_or_404(db: Session, member_id: str) -> Member:
    try:
        member_uuid = UUID(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid member ID") from exc

    member = db.query(Member).filter(Member.id == member_uuid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.get("", response_model=list[MemberRead])
def list_members(
    university_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    visible_statuses, _ = _member_access_scope(db, user)
    query = db.query(Member).order_by(Member.created_at.desc())
    if scoped_university_id:
        query = query.filter(Member.university_id == scoped_university_id)
    if visible_statuses:
        query = query.filter(Member.status.in_(visible_statuses))
    return [_serialize(item) for item in query.all()]


@router.get("/alumni-connect", response_model=list[AlumniConnectRead])
def list_alumni_connect(
    university_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role(GENERAL_NETWORK_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, university_id)
    query = (
        db.query(Member)
        .filter(Member.status == "Alumni")
        .order_by(Member.last_name.asc(), Member.first_name.asc(), Member.created_at.desc())
    )
    if scoped_university_id:
        query = query.filter(Member.university_id == scoped_university_id)
    return [_serialize_alumni_connect(item) for item in query.all()]


@router.get("/me-profile", response_model=MemberRead)
def get_my_profile(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _serialize(_linked_member_or_404(user, db))


@router.patch("/me-profile", response_model=MemberRead)
def update_my_profile(
    payload: MemberSelfProfileUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    member = _linked_member_or_404(user, db)
    updates = payload.model_dump(exclude_unset=True)
    for field in ["employment_status", "employer_name", "current_city", "services_offered", "products_supplied"]:
        if field in updates and isinstance(updates[field], str):
            updates[field] = updates[field].strip() or None

    for key, value in updates.items():
        setattr(member, key, value)
    db.commit()
    db.refresh(member)
    log_action(db, user.id, "update", "member_self_profile", str(member.id), {"email": member.email})
    return _serialize(member)


@router.post("", response_model=MemberRead)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    scoped_university_id = resolve_university_scope(user, payload.university_id)
    _, writable_statuses = _member_access_scope(db, user)
    payload_data = payload.model_dump(exclude={"university_id"})
    payload_data["status"] = _normalize_member_status_for_user(payload.status, writable_statuses)
    payload_data["program_of_study_id"] = _resolve_program_of_study(
        db,
        scoped_university_id,
        payload.program_of_study_id,
    )
    member = Member(
        **payload_data,
        university_id=scoped_university_id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    log_action(db, user.id, "create", "member", str(member.id), {"email": member.email})
    return _serialize(member)


@router.patch("/{member_id}", response_model=MemberRead)
def update_member(
    member_id: str,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    member = _member_by_id_or_404(db, member_id)

    target_university_id = payload.university_id or member.university_id
    scoped_university_id = resolve_university_scope(user, target_university_id)
    visible_statuses, writable_statuses = _member_access_scope(db, user)
    _ensure_member_visible(member.status, visible_statuses)
    _ensure_member_writable(member.status, writable_statuses)

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        updates["status"] = _normalize_member_status_for_user(updates.get("status"), writable_statuses)
    if "program_of_study_id" in updates:
        updates["program_of_study_id"] = _resolve_program_of_study(
            db,
            scoped_university_id,
            updates.get("program_of_study_id"),
        )
    elif "university_id" in updates and scoped_university_id != member.university_id:
        updates["program_of_study_id"] = None

    for key, value in updates.items():
        setattr(member, key, value)
    db.commit()
    db.refresh(member)
    log_action(db, user.id, "update", "member", str(member.id), {"email": member.email})
    return _serialize(member)


@router.delete("/{member_id}")
def delete_member(
    member_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    member = _member_by_id_or_404(db, member_id)
    resolve_university_scope(user, member.university_id)
    visible_statuses, writable_statuses = _member_access_scope(db, user)
    _ensure_member_visible(member.status, visible_statuses)
    _ensure_member_writable(member.status, writable_statuses)

    db.delete(member)
    db.commit()
    log_action(db, user.id, "delete", "member", str(member_id), None)
    return {"status": "deleted"}


@router.post("/bulk-upload")
def bulk_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(CHAPTER_ROLES)),
):
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    created = 0
    _, writable_statuses = _member_access_scope(db, user)

    for row in reader:
        row_university_id = int(row.get("university_id") or 0)
        scoped_university_id = resolve_university_scope(user, row_university_id)
        member = Member(
            member_id=row.get("member_id"),
            first_name=row.get("first_name") or "",
            last_name=row.get("last_name") or "",
            gender=row.get("gender"),
            phone=row.get("phone"),
            email=row.get("email"),
            university_id=scoped_university_id,
            program_of_study_id=_resolve_program_of_study(
                db,
                scoped_university_id,
                int(row.get("program_of_study_id")) if row.get("program_of_study_id") else None,
                row.get("program_of_study_name"),
            ),
            start_year=int(row.get("start_year")) if row.get("start_year") else None,
            expected_graduation_date=row.get("expected_graduation_date") or None,
            intake=row.get("intake"),
            status=_normalize_member_status_for_user(row.get("status"), writable_statuses),
            employment_status=row.get("employment_status"),
            employer_name=row.get("employer_name"),
            current_city=row.get("current_city"),
            active=(row.get("active", "true").lower() == "true"),
        )
        db.add(member)
        created += 1

    db.commit()
    log_action(db, user.id, "bulk_upload", "member", None, {"created": created})
    return {"created": created}
