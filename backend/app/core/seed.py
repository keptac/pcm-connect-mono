from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import (
    AcademicProgram,
    BroadcastInvite,
    CampusEvent,
    Conference,
    FundingRecord,
    MarketplaceListing,
    MandatoryProgram,
    Member,
    Program,
    ProgramBroadcast,
    ProgramUpdate,
    ReportingPeriod,
    Role,
    Union,
    University,
    User,
    UserRole,
)
from .config import settings
from .security import hash_password
from .zimbabwe_academic_catalog import ZIMBABWE_ACADEMIC_INSTITUTION_SPECS, build_academic_program_specs, normalize_academic_program_name

DEFAULT_ROLES = ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin", "general_user", "service_recovery"]
ACADEMIC_SPEC_BY_NAME = {spec["name"]: spec for spec in ZIMBABWE_ACADEMIC_INSTITUTION_SPECS}
DEFAULT_UNION_NAME = "Zimbabwe East Union Conference"
DEFAULT_UNION_SPECS = [
    {"name": "Zimbabwe Central Union Conference"},
    {"name": "Zimbabwe East Union Conference"},
    {"name": "Zimbabwe West Union Conference"},
]
DEFAULT_CONFERENCE_SPECS = [
    {"name": "North Zimbabwe Conference", "union_name": "Zimbabwe East Union Conference"},
    {"name": "East Zimbabwe Conference", "union_name": "Zimbabwe East Union Conference"},
    {"name": "South Zimbabwe Conference", "union_name": "Zimbabwe West Union Conference"},
    {"name": "Central Zimbabwe Conference", "union_name": "Zimbabwe Central Union Conference"},
]
REPORTING_PERIOD_SPECS = [
    {
        "code": "2026-S1",
        "label": "2026 Semester 1",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 6, 30),
        "sort_order": 10,
    },
    {
        "code": "2026-S2",
        "label": "2026 Semester 2",
        "start_date": date(2026, 7, 1),
        "end_date": date(2026, 12, 31),
        "sort_order": 20,
    },
]
LEGACY_MARKETPLACE_DEMO_EMAILS = [
    "marketplace.supplier@pcm.local",
    "marketplace.coordinator@pcm.local",
]
LEGACY_REPORTING_PERIOD_CODES = [
    "2026-Q1",
    "2026-Q2",
    "2026-Q3",
    "2026-Q4",
]


def _modernize_terminology(value: str | None) -> str | None:
    if value is None:
        return None

    replacements = [
        ("chapter leaders", "campus leaders"),
        ("chapter staff", "campus staff"),
        ("chapter alumni", "campus alumni"),
        ("chapter programming", "campus programming"),
        ("chapter objectives", "campus objectives"),
        ("chapter team", "campus team"),
        ("chapter subscriptions", "campus subscriptions"),
        ("university chapter", "university or campus"),
        ("nearby chapters", "nearby campuses"),
        ("chapter-led", "campus-led"),
        ("Chapter Team", "Campus Team"),
        ("Chapter Zunde Drive", "Campus Zunde Drive"),
        ("Chapter subscriptions", "Campus subscriptions"),
        ("Chapter", "Campus"),
        ("chapter", "campus"),
        ("Chapters", "Campuses"),
        ("chapters", "campuses"),
    ]

    updated = value
    for source, target in replacements:
        updated = updated.replace(source, target)
    return updated

ZIMBABWE_CHAPTER_SPECS = [
    {
        "name": "University of Zimbabwe",
        "short_code": "UZ",
        "country": "Zimbabwe",
        "city": "Harare",
        "region": "Harare Metropolitan",
        "mission_focus": "Student leadership formation, discipleship, and urban outreach.",
        "contact_name": "Ruth Chikore",
        "contact_email": "uz@pcm.local",
        "contact_phone": "+263771000101",
        "programs": [
            {
                "name": "Student Leadership Incubator",
                "category": "Leadership",
                "status": "active",
                "description": "Develops campus leaders, fellowship coordinators, and peer mentors across faculties.",
                "manager_name": "Ruth Chikore",
                "target_beneficiaries": 180,
                "beneficiaries_served": 126,
                "annual_budget": 22000,
                "duration_months": 12,
                "level": "University",
                "start_date": date(2026, 1, 12),
            },
            {
                "name": "Harare Prayer and Care Rooms",
                "category": "Pastoral Care",
                "status": "active",
                "description": "Provides weekly pastoral care, counseling referrals, and prayer spaces for students.",
                "manager_name": "Tatenda Moyo",
                "target_beneficiaries": 110,
                "beneficiaries_served": 74,
                "annual_budget": 9800,
                "duration_months": 10,
                "level": "University",
                "start_date": date(2026, 2, 3),
            },
        ],
    },
    {
        "name": "National University of Science and Technology",
        "short_code": "NUST",
        "country": "Zimbabwe",
        "city": "Bulawayo",
        "region": "Bulawayo Metropolitan",
        "mission_focus": "Integrating innovation, mentorship, and holistic student support.",
        "contact_name": "Mandla Ncube",
        "contact_email": "nust@pcm.local",
        "contact_phone": "+263771000102",
        "programs": [
            {
                "name": "Innovation and Mentorship Labs",
                "category": "Mentorship",
                "status": "active",
                "description": "Pairs students with ministry, business, and professional mentors in technical fields.",
                "manager_name": "Mandla Ncube",
                "target_beneficiaries": 140,
                "beneficiaries_served": 96,
                "annual_budget": 16500,
                "duration_months": 11,
                "level": "University",
                "start_date": date(2026, 1, 17),
            },
            {
                "name": "Residence Hall Bible Circles",
                "category": "Discipleship",
                "status": "active",
                "description": "Small-group discipleship circles rooted in residence halls and hostels.",
                "manager_name": "Nokuthula Dube",
                "target_beneficiaries": 125,
                "beneficiaries_served": 89,
                "annual_budget": 8700,
                "duration_months": 12,
                "level": "Campus",
                "start_date": date(2026, 1, 7),
            },
        ],
    },
    {
        "name": "Midlands State University",
        "short_code": "MSU",
        "country": "Zimbabwe",
        "city": "Gweru",
        "region": "Midlands",
        "mission_focus": "Building servant leaders and equipping students for work, witness, and community service.",
        "contact_name": "Tariro Hove",
        "contact_email": "msu@pcm.local",
        "contact_phone": "+263771000103",
        "programs": [
            {
                "name": "Marketplace Discipleship Track",
                "category": "Leadership",
                "status": "active",
                "description": "Prepares finalists and graduates for ethical leadership in workplaces and local churches.",
                "manager_name": "Tariro Hove",
                "target_beneficiaries": 95,
                "beneficiaries_served": 61,
                "annual_budget": 11200,
                "duration_months": 9,
                "level": "University",
                "start_date": date(2026, 1, 20),
            },
            {
                "name": "Community Outreach Saturdays",
                "category": "Outreach",
                "status": "active",
                "description": "Mobilizes volunteers for nearby school support, food hampers, and evangelistic outreach.",
                "manager_name": "Brighton Mlambo",
                "target_beneficiaries": 170,
                "beneficiaries_served": 118,
                "annual_budget": 15400,
                "duration_months": 12,
                "level": "Campus",
                "start_date": date(2026, 2, 1),
            },
        ],
    },
    {
        "name": "Great Zimbabwe University",
        "short_code": "GZU",
        "country": "Zimbabwe",
        "city": "Masvingo",
        "region": "Masvingo",
        "mission_focus": "Extending compassionate ministry, discipleship, and rural mission engagement.",
        "contact_name": "Fadzai Mhundwa",
        "contact_email": "gzu@pcm.local",
        "contact_phone": "+263771000104",
        "programs": [
            {
                "name": "Rural Campus Mission Teams",
                "category": "Mission",
                "status": "active",
                "description": "Deploys teams to surrounding communities for student ministry and church partnership work.",
                "manager_name": "Fadzai Mhundwa",
                "target_beneficiaries": 150,
                "beneficiaries_served": 102,
                "annual_budget": 14200,
                "duration_months": 10,
                "level": "Regional",
                "start_date": date(2026, 1, 24),
            },
            {
                "name": "Heritage Counseling Desk",
                "category": "Pastoral Care",
                "status": "active",
                "description": "Offers structured care, mentorship, and referral support for students facing pressure and transition.",
                "manager_name": "Simbarashe Jari",
                "target_beneficiaries": 85,
                "beneficiaries_served": 53,
                "annual_budget": 7900,
                "duration_months": 12,
                "level": "University",
                "start_date": date(2026, 2, 8),
            },
        ],
    },
    {
        "name": "Chinhoyi University of Technology",
        "short_code": "CUT",
        "country": "Zimbabwe",
        "city": "Chinhoyi",
        "region": "Mashonaland West",
        "mission_focus": "Using innovation, service, and student support to strengthen witness on campus.",
        "contact_name": "Joyline Marufu",
        "contact_email": "cut@pcm.local",
        "contact_phone": "+263771000105",
        "programs": [
            {
                "name": "Tech for Good Fellows",
                "category": "Innovation",
                "status": "active",
                "description": "Supports students building service projects and digital tools for community impact.",
                "manager_name": "Joyline Marufu",
                "target_beneficiaries": 120,
                "beneficiaries_served": 82,
                "annual_budget": 17600,
                "duration_months": 11,
                "level": "University",
                "start_date": date(2026, 1, 14),
            },
            {
                "name": "Freshers Welcome Network",
                "category": "Care",
                "status": "active",
                "description": "Provides onboarding, first-semester care groups, and peer support for new students.",
                "manager_name": "Clive Chiweshe",
                "target_beneficiaries": 210,
                "beneficiaries_served": 149,
                "annual_budget": 9300,
                "duration_months": 8,
                "level": "Campus",
                "start_date": date(2026, 2, 2),
            },
        ],
    },
    {
        "name": "Africa University",
        "short_code": "AU",
        "country": "Zimbabwe",
        "city": "Mutare",
        "region": "Manicaland",
        "mission_focus": "Cross-border leadership formation, community impact, and student ministry in a multicultural setting.",
        "contact_name": "Priscilla Mlambo",
        "contact_email": "africauni@pcm.local",
        "contact_phone": "+263771000106",
        "programs": [
            {
                "name": "Cross-Border Leadership Forum",
                "category": "Leadership",
                "status": "active",
                "description": "Equips regional student leaders for ministry across cultures and campuses.",
                "manager_name": "Priscilla Mlambo",
                "target_beneficiaries": 105,
                "beneficiaries_served": 67,
                "annual_budget": 14800,
                "duration_months": 12,
                "level": "Regional",
                "start_date": date(2026, 1, 18),
            },
            {
                "name": "Women in Ministry Growth Circle",
                "category": "Mentorship",
                "status": "active",
                "description": "Creates mentoring groups and leadership coaching for women serving in ministry contexts.",
                "manager_name": "Sarah Nyoni",
                "target_beneficiaries": 75,
                "beneficiaries_served": 44,
                "annual_budget": 8400,
                "duration_months": 9,
                "level": "University",
                "start_date": date(2026, 2, 6),
            },
        ],
    },
    {
        "name": "Bindura University of Science Education",
        "short_code": "BUSE",
        "country": "Zimbabwe",
        "city": "Bindura",
        "region": "Mashonaland Central",
        "mission_focus": "Serving education-focused students through mentoring, discipleship, and outreach.",
        "contact_name": "Tawanda Gatsi",
        "contact_email": "buse@pcm.local",
        "contact_phone": "+263771000107",
        "programs": [
            {
                "name": "Education Mentors Network",
                "category": "Mentorship",
                "status": "active",
                "description": "Pairs future educators with mentors while forming school-based ministry teams.",
                "manager_name": "Tawanda Gatsi",
                "target_beneficiaries": 130,
                "beneficiaries_served": 91,
                "annual_budget": 12600,
                "duration_months": 10,
                "level": "University",
                "start_date": date(2026, 1, 21),
            },
            {
                "name": "Science Outreach Caravan",
                "category": "Outreach",
                "status": "active",
                "description": "Combines school science support, mentorship, and gospel-centered community engagement.",
                "manager_name": "Nomsa Chikodzi",
                "target_beneficiaries": 190,
                "beneficiaries_served": 133,
                "annual_budget": 16800,
                "duration_months": 12,
                "level": "Regional",
                "start_date": date(2026, 2, 4),
            },
        ],
    },
]

MANDATORY_EVENT_SPECS = [
    {"name": "Zunde on campus", "sort_order": 10},
    {"name": "Zunde off campus", "sort_order": 20},
    {"name": "Health expo", "sort_order": 30},
    {"name": "Orientation", "sort_order": 40},
    {"name": "Freshman camp", "sort_order": 50},
    {"name": "Meeting", "sort_order": 80},
    {"name": "Other", "sort_order": 999, "allow_other_detail": True},
]
LEGACY_MANDATORY_EVENT_NAMES = [
    "Book distribution",
    "Medical missionary",
    "Medical Missional",
]

BROADCAST_SPECS = [
    {
        "host_university": "University of Zimbabwe",
        "program_name": "Student Leadership Incubator",
        "title": "PCM Zimbabwe Leadership Exchange Week",
        "summary": "A broadcast invitation for campus leaders across the network to join a shared leadership formation week with workshops, worship, and peer learning.",
        "venue": "University of Zimbabwe Great Hall",
        "visibility": "network",
        "status": "open",
        "starts_at": datetime(2026, 4, 18, 9, 0, 0),
        "ends_at": datetime(2026, 4, 19, 17, 0, 0),
    },
    {
        "host_university": "National University of Science and Technology",
        "program_name": "Innovation and Mentorship Labs",
        "title": "Innovation for Ministry Hack Session",
        "summary": "NUST is inviting selected campuses to co-build student-led digital tools, mentorship structures, and reporting workflows for ministry impact.",
        "venue": "NUST Innovation Hub",
        "visibility": "targeted",
        "status": "open",
        "starts_at": datetime(2026, 4, 24, 10, 0, 0),
        "ends_at": datetime(2026, 4, 24, 16, 0, 0),
        "invited_universities": [
            "University of Zimbabwe",
            "Midlands State University",
            "Bindura University of Science Education",
        ],
        "invite_statuses": {
            "University of Zimbabwe": "accepted",
            "Midlands State University": "interested",
            "Bindura University of Science Education": "invited",
        },
    },
    {
        "host_university": "Africa University",
        "program_name": "Cross-Border Leadership Forum",
        "title": "Regional Prayer and Alumni Connections Summit",
        "summary": "Africa University is broadcasting a prayer and alumni networking summit that welcomes nearby campuses for ministry exchange and regional partner engagement.",
        "venue": "Africa University Prayer Garden",
        "visibility": "targeted",
        "status": "open",
        "starts_at": datetime(2026, 5, 7, 8, 30, 0),
        "ends_at": datetime(2026, 5, 7, 15, 30, 0),
        "invited_universities": [
            "Great Zimbabwe University",
            "Chinhoyi University of Technology",
            "Bindura University of Science Education",
        ],
        "invite_statuses": {
            "Great Zimbabwe University": "accepted",
            "Chinhoyi University of Technology": "invited",
            "Bindura University of Science Education": "declined",
        },
    },
]


def _chapter_code(name: str) -> str:
    parts = [segment[0].upper() for segment in name.split() if segment]
    return "".join(parts[:4]) or "PCM"


def _ensure_conference(db: Session, spec: dict) -> Conference:
    union = _ensure_union(db, spec["union_name"])
    conference = db.query(Conference).filter(Conference.name == spec["name"]).first()
    if not conference:
        conference = Conference(
            name=spec["name"],
            union_name=spec["union_name"],
            union_id=union.id,
            is_active=True,
        )
        db.add(conference)
        db.commit()
        db.refresh(conference)
        return conference

    conference.union_name = spec["union_name"]
    conference.union_id = union.id
    if conference.is_active is None:
        conference.is_active = True
    db.commit()
    db.refresh(conference)
    return conference


def _ensure_default_conferences(db: Session) -> dict[str, Conference]:
    return {spec["name"]: _ensure_conference(db, spec) for spec in DEFAULT_CONFERENCE_SPECS}


def _ensure_union(db: Session, union_name: str) -> Union:
    union = db.query(Union).filter(Union.name == union_name).first()
    if not union:
        union = Union(name=union_name, is_active=True)
        db.add(union)
        db.commit()
        db.refresh(union)
        return union

    if union.is_active is None:
        union.is_active = True
        db.commit()
        db.refresh(union)
    return union


def _ensure_default_unions(db: Session) -> dict[str, Union]:
    return {spec["name"]: _ensure_union(db, spec["name"]) for spec in DEFAULT_UNION_SPECS}


def _infer_conference_name(spec: dict | None, university: University | None = None) -> str:
    region = (spec.get("region") if spec else None) or (university.region if university else "") or ""
    city = (spec.get("city") if spec else None) or (university.city if university else "") or ""
    region_value = region.lower()
    city_value = city.lower()

    if "manicaland" in region_value or "mutare" in city_value:
        return "East Zimbabwe Conference"
    if "midlands" in region_value or "masvingo" in region_value or "gweru" in city_value or "kwekwe" in city_value:
        return "Central Zimbabwe Conference"
    if "bulawayo" in region_value or "matabeleland" in region_value or city_value in {"bulawayo", "gwanda", "lupane", "esigodini", "beitbridge"}:
        return "South Zimbabwe Conference"
    return "North Zimbabwe Conference"


def _ensure_role(db: Session, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name)
        db.add(role)
        db.commit()
        db.refresh(role)
    return role


def _ensure_user_role(db: Session, user: User, role_name: str) -> None:
    role = _ensure_role(db, role_name)
    existing = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
    if not existing:
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()


def _set_exact_user_roles(db: Session, user: User, role_names: list[str]) -> None:
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.flush()
    for role_name in role_names:
        role = _ensure_role(db, role_name)
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def _ensure_chapter_manager(db: Session, university: University) -> User:
    manager_email = f"{(university.short_code or _chapter_code(university.name)).lower()}@pcm.local"
    manager = db.query(User).filter(User.email == manager_email).first()
    if not manager:
        manager = User(
            email=manager_email,
            name=f"{university.name} Coordinator",
            password_hash=hash_password("chapter123"),
            university_id=university.id,
            is_active=True,
        )
        db.add(manager)
        db.commit()
        db.refresh(manager)
    elif manager.university_id != university.id:
        manager.university_id = university.id
        db.commit()
        db.refresh(manager)

    _ensure_user_role(db, manager, "student_admin")
    return manager


def _ensure_alumni_admin(db: Session, university: University) -> User:
    short_code = (university.short_code or _chapter_code(university.name)).lower()
    alumni_admin_email = f"alumniadmin.{short_code}@pcm.local"
    alumni_admin = db.query(User).filter(User.email == alumni_admin_email).first()
    if not alumni_admin:
        alumni_admin = User(
            email=alumni_admin_email,
            name=f"{university.name} Alumni Admin",
            password_hash=hash_password("chapter123"),
            university_id=university.id,
            is_active=True,
        )
        db.add(alumni_admin)
        db.commit()
        db.refresh(alumni_admin)
    elif alumni_admin.university_id != university.id:
        alumni_admin.university_id = university.id
        db.commit()
        db.refresh(alumni_admin)

    _ensure_user_role(db, alumni_admin, "alumni_admin")
    return alumni_admin


def _ensure_university_profile(db: Session, spec: dict) -> University:
    university = db.query(University).filter(University.name == spec["name"]).first()
    if not university:
        university = University(name=spec["name"])
        db.add(university)
        db.commit()
        db.refresh(university)

    for field in [
        "short_code",
        "country",
        "city",
        "region",
        "mission_focus",
        "contact_name",
        "contact_email",
        "contact_phone",
    ]:
        current_value = getattr(university, field)
        next_value = spec.get(field)
        if not current_value and next_value:
            setattr(university, field, next_value)

    if university.is_active is None:
        university.is_active = True
    university.contact_name = university.contact_name or "Admissions Office"
    university.contact_phone = university.contact_phone or "+263710000000"

    conference_name = spec.get("conference_name") or _infer_conference_name(spec, university)
    conference = db.query(Conference).filter(Conference.name == conference_name).first()
    if conference and university.conference_id is None:
        university.conference_id = conference.id

    db.commit()
    db.refresh(university)
    return university


def _merge_academic_program_catalog(
    db: Session,
    university: University,
) -> dict[str, AcademicProgram]:
    catalog: dict[str, AcademicProgram] = {}
    for program in (
        db.query(AcademicProgram)
        .filter(AcademicProgram.university_id == university.id)
        .order_by(AcademicProgram.id.asc())
        .all()
    ):
        normalized_name = normalize_academic_program_name(program.name)
        if not normalized_name:
            continue

        canonical = catalog.get(normalized_name)
        if not canonical:
            catalog[normalized_name] = program
            continue

        for field in ("faculty", "study_area", "qualification_level"):
            if getattr(canonical, field) in (None, "") and getattr(program, field) not in (None, ""):
                setattr(canonical, field, getattr(program, field))

        if not canonical.is_active and program.is_active:
            canonical.is_active = True

        for member in list(program.members):
            member.program_of_study = canonical

        db.delete(program)

    return catalog


def _ensure_academic_programs_for_university(
    db: Session,
    university: University,
) -> list[AcademicProgram]:
    spec = ACADEMIC_SPEC_BY_NAME.get(university.name)
    if spec:
        program_specs = build_academic_program_specs(spec)
    else:
        program_specs = build_academic_program_specs({"program_groups": ["business", "computing", "education", "humanities"]})

    existing_catalog = _merge_academic_program_catalog(db, university)
    db.flush()
    created: list[AcademicProgram] = []
    for program_spec in program_specs:
        cleaned_spec = dict(program_spec)
        cleaned_spec["name"] = " ".join(cleaned_spec["name"].split())
        normalized_name = normalize_academic_program_name(cleaned_spec["name"])
        if not normalized_name:
            continue

        program = existing_catalog.get(normalized_name)
        if not program:
            program = AcademicProgram(university_id=university.id, **cleaned_spec)
            db.add(program)
            db.flush()
            existing_catalog[normalized_name] = program
        else:
            if program.name != cleaned_spec["name"]:
                program.name = cleaned_spec["name"]
            for field, value in cleaned_spec.items():
                current_value = getattr(program, field)
                if current_value in (None, "") and value not in (None, ""):
                    setattr(program, field, value)
                if field == "is_active" and value and not current_value:
                    setattr(program, field, value)

        created.append(program)

    db.commit()
    for program in created:
        db.refresh(program)
    return created


def _ensure_program(db: Session, university: University, program_spec: dict) -> Program:
    cleaned_spec = dict(program_spec)
    legacy_duration_months = cleaned_spec.pop("duration_months", None)
    if cleaned_spec.get("duration_weeks") in (None, "") and legacy_duration_months not in (None, ""):
        cleaned_spec["duration_weeks"] = float(legacy_duration_months) * 4

    program = (
        db.query(Program)
        .filter(Program.university_id == university.id, Program.name == cleaned_spec["name"])
        .first()
    )
    if not program:
        program = Program(university_id=university.id, **cleaned_spec)
        db.add(program)
        db.commit()
        db.refresh(program)
        return program

    for field, value in cleaned_spec.items():
        current_value = getattr(program, field)
        if current_value in (None, ""):
            setattr(program, field, value)

    db.commit()
    db.refresh(program)
    return program


def _ensure_members(
    db: Session,
    university: University,
    academic_programs: list[AcademicProgram],
    ministry_program: Program | None = None,
) -> None:
    short_code = university.short_code or _chapter_code(university.name)
    member_specs = [
        {
            "member_id": f"{short_code}-001",
            "first_name": "Faith",
            "last_name": "Muchengeti",
            "email": f"faith.{short_code.lower()}@pcm.local",
            "phone": "+263772100201",
            "start_year": 2024,
            "status": "Volunteer",
            "study_index": 0,
            "active": True,
        },
        {
            "member_id": f"{short_code}-002",
            "first_name": "Prince",
            "last_name": "Ndlovu",
            "email": f"prince.{short_code.lower()}@pcm.local",
            "phone": "+263772100202",
            "start_year": 2023,
            "status": "Student",
            "study_index": 1,
            "active": True,
        },
        {
            "member_id": f"{short_code}-003",
            "first_name": "Tariro",
            "last_name": "Mupfumi",
            "email": f"alumni.{short_code.lower()}@pcm.local",
            "phone": "+263772100203",
            "start_year": 2020,
            "expected_graduation_date": date(2024, 11, 30),
            "status": "Alumni",
            "employment_status": "Employed",
            "employer_name": f"{university.city} Community Initiative",
            "current_city": university.city,
            "services_offered": "Career mentorship, CV reviews, project consulting",
            "products_supplied": "Training materials, branded outreach kits",
            "study_index": 2,
            "active": True,
        },
        {
            "member_id": f"{short_code}-004",
            "first_name": "Ropafadzo",
            "last_name": "Chari",
            "email": f"student.{short_code.lower()}@pcm.local",
            "phone": "+263772100204",
            "start_year": 2025,
            "status": "Student",
            "study_index": 3,
            "active": True,
        },
        {
            "member_id": f"{short_code}-005",
            "first_name": "Noel",
            "last_name": "Sibanda",
            "email": f"staff.{short_code.lower()}@pcm.local",
            "phone": "+263772100205",
            "start_year": 2021,
            "status": "Staff",
            "services_offered": "Event coordination, logistics support",
            "products_supplied": "Office supplies, print coordination",
            "study_index": None,
            "active": True,
        },
    ]

    for member_spec in member_specs:
        study_index = member_spec.pop("study_index")
        assigned_program = None
        if study_index is not None and academic_programs:
            assigned_program = academic_programs[min(study_index, len(academic_programs) - 1)]

        member = db.query(Member).filter(Member.member_id == member_spec["member_id"]).first()
        if not member:
            db.add(
                Member(
                    university_id=university.id,
                    program_id=ministry_program.id if ministry_program else None,
                    program_of_study_id=assigned_program.id if assigned_program else None,
                    **member_spec,
                )
            )
            continue

        if member.university_id != university.id:
            member.university_id = university.id
        if not member.program_id and ministry_program:
            member.program_id = ministry_program.id
        if not member.program_of_study_id and assigned_program:
            member.program_of_study_id = assigned_program.id

        for field, value in member_spec.items():
            current_value = getattr(member, field)
            if current_value in (None, ""):
                setattr(member, field, value)

    db.commit()


def _ensure_program_events(
    db: Session,
    university: University,
    manager: User,
    program: Program,
    index: int,
) -> None:
    event_specs = [
        {
            "title": f"{program.name} planning workshop",
            "event_type": "Workshop",
            "audience": "Students and campus staff",
            "status": "scheduled",
            "venue": f"{university.name} Main Hall",
            "description": f"Planning session for the next delivery phase of {program.name}.",
            "organizer_name": manager.name or f"{university.name} Campus Team",
            "starts_at": datetime(2026, 4, min(25, 4 + index), 16, 0, 0),
            "ends_at": datetime(2026, 4, min(25, 4 + index), 18, 0, 0),
        },
        {
            "title": f"{program.name} community activation day",
            "event_type": "Outreach",
            "audience": "Students, alumni, and partners",
            "status": "scheduled",
            "venue": f"{university.city} Community Hub",
            "description": f"Service day linked to {program.name} with campus alumni and volunteers.",
            "organizer_name": manager.name or f"{university.name} Campus Team",
            "starts_at": datetime(2026, 4, min(28, 12 + index), 9, 0, 0),
            "ends_at": datetime(2026, 4, min(28, 12 + index), 13, 0, 0),
        },
    ]

    for event_spec in event_specs:
        event = (
            db.query(CampusEvent)
            .filter(
                CampusEvent.university_id == university.id,
                CampusEvent.program_id == program.id,
                CampusEvent.title == event_spec["title"],
            )
            .first()
        )
        if not event:
            db.add(
                CampusEvent(
                    university_id=university.id,
                    program_id=program.id,
                    created_by=manager.id,
                    **event_spec,
                )
            )
            continue

        if event.created_by is None:
            event.created_by = manager.id

        for field, value in event_spec.items():
            current_value = getattr(event, field)
            if current_value in (None, ""):
                setattr(event, field, value)

    db.commit()


def _ensure_program_update(
    db: Session,
    university: University,
    manager: User,
    program: Program,
    index: int,
) -> None:
    if db.query(ProgramUpdate).filter(ProgramUpdate.program_id == program.id).first():
        return

    seeded_events = [
        "Zunde on campus",
        "Health expo",
        "Orientation",
        "Freshman camp",
        "Zunde off campus",
    ]
    event_name = seeded_events[(index - 1) % len(seeded_events)]

    update = ProgramUpdate(
        university_id=university.id,
        program_id=program.id,
        title=event_name,
        event_name=event_name,
        reporting_period="2026-S1",
        reporting_date=date(2026, 3, min(28, index + 6)),
        summary=f"{program.name} is active at {university.name} and continues to grow its ministry reach.",
        outcomes="Student participation is rising and volunteer structures are stabilizing.",
        challenges="Transport, materials, and follow-up capacity still require strengthening.",
        next_steps="Improve mentor coordination, document impact stories, and deepen donor reporting.",
        beneficiaries_reached=program.beneficiaries_served or (55 + index * 5),
        volunteers_involved=7 + index,
        funds_used=(program.annual_budget or 0) * 0.22,
        submitted_by=manager.id,
    )
    db.add(update)
    program.last_update_at = datetime(2026, 3, 1, 9, 0, 0)
    db.commit()


def _ensure_mandatory_programs(db: Session, admin: User) -> None:
    for legacy_name in LEGACY_MANDATORY_EVENT_NAMES:
        db.query(MandatoryProgram).filter(
            MandatoryProgram.program_type == "event",
            MandatoryProgram.name == legacy_name,
        ).delete()

    for spec in MANDATORY_EVENT_SPECS:
        item = db.query(MandatoryProgram).filter(MandatoryProgram.name == spec["name"]).first()
        if not item:
            item = MandatoryProgram(
                name=spec["name"],
                program_type="event",
                allow_other_detail=spec.get("allow_other_detail", False),
                is_active=True,
                sort_order=spec.get("sort_order", 0),
                created_by=admin.id,
            )
            db.add(item)
            continue

        if not item.program_type:
            item.program_type = "event"
        if item.created_by is None:
            item.created_by = admin.id
        if item.sort_order in (None, 0):
            item.sort_order = spec.get("sort_order", 0)
        if spec.get("allow_other_detail") and not item.allow_other_detail:
            item.allow_other_detail = True
        if item.is_active is None:
            item.is_active = True

    for update in db.query(ProgramUpdate).all():
        if not update.event_name:
            update.event_name = update.title

    db.commit()


def _ensure_reporting_periods(db: Session, admin: User) -> None:
    active_codes = {spec["code"] for spec in REPORTING_PERIOD_SPECS}
    for legacy_code in LEGACY_REPORTING_PERIOD_CODES:
        if legacy_code in active_codes:
            continue
        db.query(ReportingPeriod).filter(ReportingPeriod.code == legacy_code).delete()

    for spec in REPORTING_PERIOD_SPECS:
        item = db.query(ReportingPeriod).filter(ReportingPeriod.code == spec["code"]).first()
        if not item:
            item = ReportingPeriod(
                code=spec["code"],
                label=spec["label"],
                start_date=spec["start_date"],
                end_date=spec["end_date"],
                is_active=True,
                sort_order=spec["sort_order"],
                created_by=admin.id,
            )
            db.add(item)
            continue

        if not item.label:
            item.label = spec["label"]
        if not item.start_date:
            item.start_date = spec["start_date"]
        if not item.end_date:
            item.end_date = spec["end_date"]
        if item.sort_order in (None, 0):
            item.sort_order = spec["sort_order"]
        if item.created_by is None:
            item.created_by = admin.id
        if item.is_active is None:
            item.is_active = True

    db.commit()


def _ensure_program_funding(
    db: Session,
    university: University,
    manager: User,
    program: Program,
    index: int,
) -> None:
    record_specs = [
        {
            "source_name": "Zimbabwe Network Partners",
            "entry_type": "donation",
            "flow_direction": "inflow",
            "receipt_category": "Donation",
            "reporting_window": "monthly",
            "amount": 4200 + (index * 350),
            "currency": "USD",
            "transaction_date": date(2026, 2, 15),
            "channel": "bank_transfer",
            "designation": program.category or "General Support",
            "notes": "Seeded partner contribution for campus programming.",
        },
        {
            "source_name": "Campus Zunde Drive",
            "entry_type": "zunde",
            "flow_direction": "inflow",
            "receipt_category": "Zunde",
            "reporting_window": "weekly",
            "amount": 900 + (index * 120),
            "currency": "USD",
            "transaction_date": date(2026, 2, 21),
            "channel": "cash",
            "designation": "Welfare support",
            "notes": "Seeded community giving record from the Zunde basket.",
        },
        {
            "source_name": "Sabbath Offering Pool",
            "entry_type": "offering",
            "flow_direction": "inflow",
            "receipt_category": "Offering",
            "reporting_window": "weekly",
            "amount": 540 + (index * 60),
            "currency": "USD",
            "transaction_date": date(2026, 2, 23),
            "channel": "cash",
            "designation": "Campus ministry support",
            "notes": "Seeded weekly offering collected by the university campus.",
        },
        {
            "source_name": "Member Subscriptions",
            "entry_type": "subscriptions",
            "flow_direction": "inflow",
            "receipt_category": "Subscriptions",
            "reporting_window": "monthly",
            "amount": 320 + (index * 45),
            "currency": "USD",
            "transaction_date": date(2026, 2, 28),
            "channel": "mobile_money",
            "designation": "Campus subscriptions",
            "notes": "Seeded monthly member subscription update.",
        },
        {
            "source_name": "Program operations",
            "entry_type": "expense",
            "flow_direction": "outflow",
            "receipt_category": "Programme Delivery",
            "reporting_window": "monthly",
            "amount": 1100 + (index * 140),
            "currency": "USD",
            "transaction_date": date(2026, 2, 27),
            "channel": "internal",
            "designation": "Field delivery",
            "notes": "Seeded delivery, transport, and materials cost.",
        },
        {
            "source_name": "Campus transport reimbursements",
            "entry_type": "expense",
            "flow_direction": "outflow",
            "receipt_category": "Transport",
            "reporting_window": "weekly",
            "amount": 280 + (index * 35),
            "currency": "USD",
            "transaction_date": date(2026, 2, 24),
            "channel": "cash",
            "designation": "Local travel",
            "notes": "Seeded transport and logistics expense record.",
        },
    ]

    for record_spec in record_specs:
        record = (
            db.query(FundingRecord)
            .filter(
                FundingRecord.program_id == program.id,
                FundingRecord.source_name == record_spec["source_name"],
                FundingRecord.transaction_date == record_spec["transaction_date"],
            )
            .first()
        )
        if not record:
            db.add(
                FundingRecord(
                    university_id=university.id,
                    program_id=program.id,
                    recorded_by=manager.id,
                    **record_spec,
                )
            )
            continue

        if record.recorded_by is None:
            record.recorded_by = manager.id

        for field, value in record_spec.items():
            current_value = getattr(record, field)
            if current_value in (None, ""):
                setattr(record, field, value)

    db.commit()


def _ensure_hq_funding(db: Session, admin: User) -> None:
    record_specs = [
        {
            "source_name": "National Partner Pledge",
            "entry_type": "donation",
            "flow_direction": "inflow",
            "receipt_category": "Donation",
            "reporting_window": "monthly",
            "amount": 12500,
            "currency": "USD",
            "transaction_date": date(2026, 3, 1),
            "channel": "bank_transfer",
            "designation": "Head office operations",
            "notes": "Seeded HQ-level partner contribution received at the national office.",
        },
        {
            "source_name": "National Office Administration",
            "entry_type": "expense",
            "flow_direction": "outflow",
            "receipt_category": "Administration",
            "reporting_window": "monthly",
            "amount": 2150,
            "currency": "USD",
            "transaction_date": date(2026, 3, 4),
            "channel": "bank_transfer",
            "designation": "Head office administration",
            "notes": "Seeded HQ-level expenditure for admin, utilities, and coordination work.",
        },
    ]

    for record_spec in record_specs:
        record = (
            db.query(FundingRecord)
            .filter(
                FundingRecord.university_id.is_(None),
                FundingRecord.source_name == record_spec["source_name"],
                FundingRecord.transaction_date == record_spec["transaction_date"],
            )
            .first()
        )
        if not record:
            db.add(FundingRecord(recorded_by=admin.id, **record_spec))
            continue

        if record.recorded_by is None:
            record.recorded_by = admin.id

        for field, value in record_spec.items():
            current_value = getattr(record, field)
            if current_value in (None, ""):
                setattr(record, field, value)

    db.commit()


def _ensure_academic_institutions(db: Session) -> None:
    for spec in ZIMBABWE_ACADEMIC_INSTITUTION_SPECS:
        university = _ensure_university_profile(db, spec)
        _ensure_academic_programs_for_university(db, university)


def _ensure_zimbabwe_chapter(db: Session, spec: dict) -> None:
    university = _ensure_university_profile(db, spec)
    academic_programs = _ensure_academic_programs_for_university(db, university)
    manager = _ensure_chapter_manager(db, university)
    _ensure_alumni_admin(db, university)

    created_programs = []
    for index, program_spec in enumerate(spec["programs"], start=1):
        program = _ensure_program(db, university, program_spec)
        created_programs.append((index, program))

    if created_programs:
        _ensure_members(db, university, academic_programs, created_programs[0][1])

    for index, program in created_programs:
        _ensure_program_update(db, university, manager, program, index)
        _ensure_program_funding(db, university, manager, program, index)
        _ensure_program_events(db, university, manager, program, index)


def _ensure_program_broadcasts(db: Session) -> None:
    for spec in BROADCAST_SPECS:
        university = db.query(University).filter(University.name == spec["host_university"]).first()
        if not university:
            continue
        manager = _ensure_chapter_manager(db, university)
        program = (
            db.query(Program)
            .filter(Program.university_id == university.id, Program.name == spec["program_name"])
            .first()
        )
        if not program:
            continue

        broadcast = (
            db.query(ProgramBroadcast)
            .filter(ProgramBroadcast.university_id == university.id, ProgramBroadcast.title == spec["title"])
            .first()
        )
        if not broadcast:
            broadcast = ProgramBroadcast(
                university_id=university.id,
                program_id=program.id,
                title=spec["title"],
                summary=_modernize_terminology(spec["summary"]),
                venue=spec["venue"],
                contact_name=manager.name,
                contact_email=manager.email,
                visibility=spec["visibility"],
                status=spec["status"],
                starts_at=spec["starts_at"],
                ends_at=spec["ends_at"],
                created_by=manager.id,
            )
            db.add(broadcast)
            db.flush()
        else:
            for field in ["summary", "venue", "visibility", "status", "starts_at", "ends_at"]:
                if getattr(broadcast, field) in (None, ""):
                    value = _modernize_terminology(spec[field]) if field == "summary" else spec[field]
                    setattr(broadcast, field, value)
            if not broadcast.program_id:
                broadcast.program_id = program.id
            if not broadcast.contact_name:
                broadcast.contact_name = manager.name
            if not broadcast.contact_email:
                broadcast.contact_email = manager.email
            if not broadcast.created_by:
                broadcast.created_by = manager.id
            broadcast.summary = _modernize_terminology(broadcast.summary)

        invited_university_names = spec.get("invited_universities", [])
        invite_statuses = spec.get("invite_statuses", {})
        desired_invites = {}
        for invited_name in invited_university_names:
            invited_university = db.query(University).filter(University.name == invited_name).first()
            if invited_university and invited_university.id != university.id:
                desired_invites[invited_university.id] = invite_statuses.get(invited_name, "invited")

        existing_by_university = {invite.university_id: invite for invite in broadcast.invites}
        for university_id, invite in list(existing_by_university.items()):
            if university_id not in desired_invites:
                db.delete(invite)

        db.flush()

        for invited_university_id, status in desired_invites.items():
            invite = existing_by_university.get(invited_university_id)
            if not invite:
                invite = BroadcastInvite(
                    broadcast_id=broadcast.id,
                    university_id=invited_university_id,
                    status=status,
                )
                if status != "invited":
                    invite.responded_at = datetime(2026, 3, 5, 10, 0, 0)
                db.add(invite)
                continue

            invite.status = status
            if status != "invited" and invite.responded_at is None:
                invite.responded_at = datetime(2026, 3, 5, 10, 0, 0)
            if status == "invited":
                invite.responded_at = None

    db.commit()


def _backfill_generic_data(db: Session, admin: User) -> None:
    member_seeded_universities = set()
    existing_programs = db.query(Program).order_by(Program.id.asc()).all()
    for index, program in enumerate(existing_programs, start=1):
        university = db.query(University).filter(University.id == program.university_id).first()
        if not university:
            continue

        if not university.short_code:
            university.short_code = _chapter_code(university.name)
        university.country = university.country or "Zimbabwe"
        university.region = university.region or "University network"
        university.mission_focus = university.mission_focus or "Leadership development and compassionate service"
        university.contact_name = university.contact_name or f"{university.name} Coordinator"
        university.contact_email = university.contact_email or f"{university.short_code.lower()}@pcm.local"
        university.contact_phone = university.contact_phone or "+263772999999"
        if university.conference_id is None:
            conference_name = _infer_conference_name(None, university)
            conference = db.query(Conference).filter(Conference.name == conference_name).first()
            if conference:
                university.conference_id = conference.id

        if program.status is None:
            program.status = "active"
        if program.category is None:
            program.category = "Leadership"
        if program.annual_budget is None:
            program.annual_budget = 10000 + (index * 1200)
        if program.beneficiaries_served is None:
            program.beneficiaries_served = 40 + (index * 7)
        if program.target_beneficiaries is None:
            program.target_beneficiaries = max((program.beneficiaries_served or 0) + 20, 60)
        if program.description is None:
            program.description = f"{program.name} advances campus objectives through mentoring, outreach, and follow-up."
        program.description = _modernize_terminology(program.description)
        if program.level == "Chapter":
            program.level = "Campus"

        manager = university.users[0] if university.users else admin
        academic_programs = _ensure_academic_programs_for_university(db, university)
        if university.id not in member_seeded_universities:
            _ensure_members(db, university, academic_programs, program)
            member_seeded_universities.add(university.id)
        _ensure_program_update(db, university, manager, program, index)
        _ensure_program_funding(db, university, manager, program, index)
        _ensure_program_events(db, university, manager, program, index)

    for university in db.query(University).order_by(University.name.asc()).all():
        if university.id in member_seeded_universities:
            continue
        academic_programs = _ensure_academic_programs_for_university(db, university)
        if academic_programs:
            _ensure_members(db, university, academic_programs)

    for event in db.query(CampusEvent).all():
        event.audience = _modernize_terminology(event.audience)
        event.description = _modernize_terminology(event.description)
        event.organizer_name = _modernize_terminology(event.organizer_name)

    for record in db.query(FundingRecord).all():
        record.source_name = _modernize_terminology(record.source_name)
        record.designation = _modernize_terminology(record.designation)
        record.notes = _modernize_terminology(record.notes)

    for broadcast in db.query(ProgramBroadcast).all():
        broadcast.summary = _modernize_terminology(broadcast.summary)

    db.commit()


def _ensure_marketplace_demo_listings(db: Session, owner: User) -> None:
    def _retire_legacy_demo_users() -> None:
        retired_user_ids: list[int] = []
        for legacy_email in LEGACY_MARKETPLACE_DEMO_EMAILS:
            user = db.query(User).filter(User.email == legacy_email).first()
            if not user:
                continue
            retired_user_ids.append(user.id)
            db.query(MarketplaceListing).filter(MarketplaceListing.user_id == user.id).update(
                {MarketplaceListing.user_id: owner.id},
                synchronize_session=False,
            )
            db.delete(user)
        if retired_user_ids:
            db.flush()

    universities = db.query(University).order_by(University.name.asc()).limit(5).all()
    if not universities:
        return

    _retire_legacy_demo_users()

    listing_specs = [
        {
            "title": "Bulk printing and banner production",
            "listing_type": "offer",
            "category": "Media and printing",
            "price_text": "Quoted per order",
            "status": "active",
            "description": "Reliable printing for outreach flyers, banners, pull-up stands, and event backdrops for PCM activities.",
            "university_index": 0,
        },
        {
            "title": "Need affordable transport for evangelism weekend",
            "listing_type": "need",
            "category": "Transport and logistics",
            "price_text": "Budget available on request",
            "status": "active",
            "description": "Looking for a trusted bus or kombi provider to move students and supplies for an off-campus mission weekend.",
            "university_index": 1,
        },
        {
            "title": "Career mentorship and CV clinic",
            "listing_type": "offer",
            "category": "Professional services",
            "price_text": "Volunteer / honorarium by arrangement",
            "status": "active",
            "description": "Support for finalists and recent graduates with CV polishing, interview coaching, LinkedIn setup, and career navigation.",
            "university_index": 2,
        },
        {
            "title": "Need branded t-shirts and caps for congress",
            "listing_type": "need",
            "category": "Apparel and merchandise",
            "price_text": "Open to supplier proposals",
            "status": "active",
            "description": "Seeking a supplier who can handle branded PCM apparel in moderate volume with reliable turnaround times.",
            "university_index": 3,
        },
        {
            "title": "Event catering and refreshment packs",
            "listing_type": "offer",
            "category": "Food and hospitality",
            "price_text": "Per head / package pricing",
            "status": "active",
            "description": "Catering support for seminars, reporting workshops, prayer retreats, and alumni networking gatherings.",
            "university_index": 4,
        },
    ]

    for spec in listing_specs:
        university = universities[min(spec["university_index"], len(universities) - 1)]
        listing = (
            db.query(MarketplaceListing)
            .filter(
                MarketplaceListing.title == spec["title"],
            )
            .first()
        )
        if not listing:
            listing = MarketplaceListing(
                user_id=owner.id,
                university_id=university.id,
                listing_type=spec["listing_type"],
                title=spec["title"],
                description=spec["description"],
                category=spec["category"],
                price_text=spec["price_text"],
                status=spec["status"],
            )
            db.add(listing)
            continue

        if listing.user_id != owner.id:
            listing.user_id = owner.id
        if not listing.university_id:
            listing.university_id = university.id
        for field in ["listing_type", "description", "category", "price_text", "status"]:
            if getattr(listing, field) in (None, ""):
                setattr(listing, field, spec[field])

    db.commit()


def seed_data(db: Session):
    for role_name in DEFAULT_ROLES:
        _ensure_role(db, role_name)

    _ensure_default_unions(db)
    _ensure_default_conferences(db)

    admin = db.query(User).filter(User.email == settings.admin_email).first()
    if not admin:
        admin = User(
            email=settings.admin_email,
            name="System Admin",
            password_hash=hash_password(settings.admin_password),
            is_active=True,
            is_system_admin=True,
            subject_to_tenure=False,
            force_password_reset=False,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    if not admin.is_system_admin or admin.subject_to_tenure:
        admin.is_system_admin = True
        admin.subject_to_tenure = False
        admin.tenure_starts_on = None
        admin.tenure_ends_on = None
        admin.disabled_at = None
        admin.deleted_at = None
        admin.is_active = True
        admin.force_password_reset = False
        db.commit()
        db.refresh(admin)
    _ensure_user_role(db, admin, "super_admin")

    recovery_account = db.query(User).filter(User.email == settings.service_recovery_email).first()
    if not recovery_account:
        recovery_account = User(
            email=settings.service_recovery_email,
            name="PCM Recovery Service",
            password_hash=hash_password(settings.service_recovery_password),
            is_active=True,
            subject_to_tenure=False,
            force_password_reset=False,
        )
        db.add(recovery_account)
        db.commit()
        db.refresh(recovery_account)
    recovery_account.name = "PCM Recovery Service"
    recovery_account.university_id = None
    recovery_account.member_id = None
    recovery_account.is_system_admin = False
    recovery_account.is_active = True
    recovery_account.subject_to_tenure = False
    recovery_account.tenure_starts_on = None
    recovery_account.tenure_ends_on = None
    recovery_account.disabled_at = None
    recovery_account.deleted_at = None
    recovery_account.force_password_reset = False
    db.commit()
    db.refresh(recovery_account)
    _set_exact_user_roles(db, recovery_account, ["service_recovery"])

    # Startup seeding should provide institution/reference data without
    # creating demo campus users or operational ministry records beyond
    # a lightweight marketplace fixture set for UI testing.
    _ensure_academic_institutions(db)
    _ensure_reporting_periods(db, admin)
    _ensure_mandatory_programs(db, admin)
    _ensure_marketplace_demo_listings(db, admin)
