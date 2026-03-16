import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import require_marketplace_access
from app.api.routes.auth import login, register_general_user, search_general_registration_matches
from app.api.routes.marketplace import (
    create_marketplace_listing,
    list_marketplace_interests,
    list_marketplace_listings,
    register_marketplace_interest,
    update_marketplace_listing,
    withdraw_marketplace_interest,
)
from app.api.routes.members import _member_access_scope, get_my_profile, list_alumni_connect, update_my_profile
from app.core.security import verify_password
from app.db.base import Base
from app.models import MarketplaceListing, Member, Role, University, User, UserRole
from app.schemas import (
    GeneralUserLookupRequest,
    GeneralUserRegisterRequest,
    LoginRequest,
    MarketplaceInterestCreate,
    MarketplaceListingCreate,
    MarketplaceListingUpdate,
    MemberSelfProfileUpdate,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_role(db_session: Session, user: User, role_name: str) -> None:
    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()


def test_general_user_registration_flow_uses_existing_member_record(db_session: Session):
    university = University(name="Example University")
    member = Member(
        id=uuid4(),
        university=university,
        first_name="Tariro",
        last_name="Moyo",
        email="tariro@example.com",
        member_id="PCM-100",
        start_year=2021,
        status="Alumni",
        active=True,
    )
    db_session.add_all([university, member])
    db_session.commit()

    matches = search_general_registration_matches(
        GeneralUserLookupRequest(last_name="Moyo", university_id=university.id, start_year=2021),
        db=db_session,
    )
    assert len(matches) == 1
    assert matches[0].member_number == "PCM-100"

    session = register_general_user(
        GeneralUserRegisterRequest(
            member_id=str(member.id),
            email="Tariro.Moyo@Example.com",
            password="secret123",
            donor_interest=True,
        ),
        db=db_session,
    )

    created_user = db_session.query(User).filter(User.member_id == member.id).first()
    assert created_user is not None
    assert created_user.university_id is None
    assert created_user.email == "tariro.moyo@example.com"
    assert created_user.donor_interest is True
    assert member.email == "tariro.moyo@example.com"
    assert verify_password("secret123", created_user.password_hash)
    assert session.user.roles == ["general_user"]
    assert session.user.member_status == "Alumni"
    assert session.sign_in_identifier == "tariro.moyo@example.com"

    login_session = login(LoginRequest(email="tariro.moyo@example.com", password="secret123"), db=db_session)
    assert login_session.access_token
    assert login_session.refresh_token

    role_names = [role.name for role in db_session.query(Role).all()]
    assert "general_user" in role_names


def test_general_user_lookup_excludes_student_profiles(db_session: Session):
    university = University(name="Example University")
    student = Member(
        id=uuid4(),
        university=university,
        first_name="Prince",
        last_name="Moyo",
        member_id="PCM-101",
        start_year=2021,
        status="Student",
        active=True,
    )
    db_session.add_all([university, student])
    db_session.commit()

    matches = search_general_registration_matches(
        GeneralUserLookupRequest(last_name="Moyo", university_id=university.id, start_year=2021),
        db=db_session,
    )
    assert matches == []


def test_general_user_lookup_requires_exact_surname_match(db_session: Session):
    university = University(name="Example University")
    member = Member(
        id=uuid4(),
        university=university,
        first_name="Tariro",
        last_name="Moyo",
        member_id="PCM-150",
        start_year=2021,
        status="Alumni",
        active=True,
    )
    db_session.add_all([university, member])
    db_session.commit()

    exact_matches = search_general_registration_matches(
        GeneralUserLookupRequest(last_name="Moyo", university_id=university.id, start_year=2021),
        db=db_session,
    )
    assert len(exact_matches) == 1

    non_exact_matches = search_general_registration_matches(
        GeneralUserLookupRequest(last_name="moyo", university_id=university.id, start_year=2021),
        db=db_session,
    )
    assert non_exact_matches == []


def test_general_user_registration_rejects_duplicate_email(db_session: Session):
    university = University(name="Example University")
    member = Member(
        id=uuid4(),
        university=university,
        first_name="Tariro",
        last_name="Moyo",
        member_id="PCM-151",
        start_year=2021,
        status="Alumni",
        active=True,
    )
    existing_user = User(
        email="taken@example.com",
        name="Existing User",
        password_hash="hashed",
    )
    db_session.add_all([university, member, existing_user])
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        register_general_user(
            GeneralUserRegisterRequest(
                member_id=str(member.id),
                email="taken@example.com",
                password="secret123",
            ),
            db=db_session,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "That email is already in use"


def test_marketplace_access_denies_student_profiles(db_session: Session):
    university = University(name="Example University")
    student_member = Member(
        id=uuid4(),
        university=university,
        first_name="Ropa",
        last_name="Chari",
        member_id="PCM-102",
        start_year=2024,
        status="Student",
        active=True,
    )
    student_user = User(
        email="student@example.com",
        name="Student User",
        password_hash="hashed",
        member=student_member,
    )
    db_session.add_all([university, student_member, student_user])
    db_session.commit()

    with pytest.raises(HTTPException):
        require_marketplace_access(student_user)


def test_member_linked_user_can_update_marketplace_profile_fields(db_session: Session):
    university = University(name="Example University")
    member = Member(
        id=uuid4(),
        university=university,
        first_name="Tariro",
        last_name="Moyo",
        member_id="PCM-103",
        start_year=2021,
        status="Alumni",
        active=True,
    )
    user = User(
        email="member@example.com",
        name="Member User",
        password_hash="hashed",
        member=member,
    )
    db_session.add_all([university, member, user])
    db_session.commit()

    updated = update_my_profile(
        MemberSelfProfileUpdate(
            employment_status="Entrepreneur",
            employer_name="Self-employed",
            current_city="Harare",
            services_offered="Graphic design, business coaching",
            products_supplied="Printed banners, branded t-shirts",
        ),
        db=db_session,
        user=user,
    )

    assert updated.employment_status == "Entrepreneur"
    assert updated.services_offered == "Graphic design, business coaching"
    assert updated.products_supplied == "Printed banners, branded t-shirts"

    fetched = get_my_profile(db=db_session, user=user)
    assert fetched.current_city == "Harare"
    assert fetched.employer_name == "Self-employed"


def test_alumni_connect_exposes_services_products_and_employer_fields(db_session: Session):
    university = University(name="Example University")
    member = Member(
        id=uuid4(),
        university=university,
        first_name="Nyasha",
        last_name="Moyo",
        member_id="PCM-104",
        start_year=2018,
        status="Alumni",
        employment_status="Employed",
        employer_name="TechWorks",
        current_city="Harare",
        services_offered="Software engineering and mentoring",
        products_supplied="Custom web applications",
        active=True,
    )
    viewer = User(
        email="viewer@example.com",
        name="Viewer User",
        password_hash="hashed",
        member=Member(
            id=uuid4(),
            university=university,
            first_name="Tadiwa",
            last_name="Ncube",
            member_id="PCM-105",
            start_year=2022,
            status="Alumni",
            active=True,
        ),
    )
    db_session.add_all([university, member, viewer])
    db_session.commit()

    alumni_rows = list_alumni_connect(db=db_session, user=viewer)
    nyasha_row = next((row for row in alumni_rows if row.member_id == "PCM-104"), None)

    assert len(alumni_rows) == 2
    assert nyasha_row is not None
    assert nyasha_row.program_of_study_name is None
    assert nyasha_row.employer_name == "TechWorks"
    assert nyasha_row.services_offered == "Software engineering and mentoring"
    assert nyasha_row.products_supplied == "Custom web applications"


def test_alumni_connect_denies_admin_and_global_scope_roles(db_session: Session):
    university = University(name="Example University")
    admin_member = Member(
        id=uuid4(),
        university=university,
        first_name="Rudo",
        last_name="Mhlanga",
        member_id="PCM-106",
        start_year=2020,
        status="Alumni",
        active=True,
    )
    admin_user = User(
        email="admin@example.com",
        name="Admin User",
        password_hash="hashed",
        member=admin_member,
    )
    db_session.add_all([university, admin_member, admin_user])
    db_session.commit()
    add_role(db_session, admin_user, "executive")

    with pytest.raises(HTTPException) as exc_info:
        list_alumni_connect(db=db_session, user=admin_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Alumni Connect is only available to student and alumni accounts"


def test_secretary_gets_student_member_scope(db_session: Session):
    university = University(name="Example University")
    user = User(
        email="secretary@example.com",
        name="Campus Secretary",
        password_hash="hashed",
        university=university,
    )
    db_session.add_all([university, user])
    db_session.commit()
    add_role(db_session, user, "secretary")

    visible_statuses, writable_statuses = _member_access_scope(db_session, user)

    assert visible_statuses == {"Student"}
    assert writable_statuses == {"Student"}


def test_global_role_can_post_marketplace_listing_for_a_university(db_session: Session):
    represented_university = University(name="Represented Campus")
    home_university = University(name="Home Campus")
    user = User(
        email="director@example.com",
        name="Director User",
        password_hash="hashed",
        university=home_university,
    )
    db_session.add_all([represented_university, home_university, user])
    db_session.commit()
    add_role(db_session, user, "director")

    created = create_marketplace_listing(
        MarketplaceListingCreate(
            university_id=represented_university.id,
            listing_type="offer",
            title="Campus-wide transport support",
            description="Transport coordination for a represented campus event.",
            category="Transport",
            price_text="By arrangement",
        ),
        db=db_session,
        user=user,
    )

    assert created.university_id == represented_university.id
    assert created.university_name == "Represented Campus"


def test_non_global_user_can_only_post_marketplace_listing_for_self(db_session: Session):
    represented_university = University(name="Represented Campus")
    home_university = University(name="Home Campus")
    user = User(
        email="admin@example.com",
        name="Campus Admin",
        password_hash="hashed",
        university=home_university,
    )
    db_session.add_all([represented_university, home_university, user])
    db_session.commit()
    add_role(db_session, user, "student_admin")

    with pytest.raises(HTTPException) as exc_info:
        create_marketplace_listing(
            MarketplaceListingCreate(
                university_id=represented_university.id,
                listing_type="need",
                title="Need event branding",
                description="Looking for fast turn-around branding support.",
            ),
            db=db_session,
            user=user,
        )

    assert exc_info.value.status_code == 403

    created = create_marketplace_listing(
        MarketplaceListingCreate(
            listing_type="need",
            title="Need event branding",
            description="Looking for fast turn-around branding support.",
        ),
        db=db_session,
        user=user,
    )

    stored = db_session.query(MarketplaceListing).filter(MarketplaceListing.id == created.id).first()
    assert stored is not None
    assert stored.university_id is None
    assert created.university_name == "Home Campus"

    with pytest.raises(HTTPException) as update_exc_info:
        update_marketplace_listing(
            created.id,
            MarketplaceListingUpdate(university_id=represented_university.id),
            db=db_session,
            user=user,
        )

    assert update_exc_info.value.status_code == 403


def test_listing_owner_can_see_registered_interest_and_supplier_details(db_session: Session):
    university = University(name="Example University")
    owner_member = Member(
        id=uuid4(),
        university=university,
        first_name="Ruth",
        last_name="Ncube",
        member_id="PCM-201",
        start_year=2020,
        status="Alumni",
        active=True,
    )
    responder_member = Member(
        id=uuid4(),
        university=university,
        first_name="Blessing",
        last_name="Moyo",
        member_id="PCM-202",
        start_year=2019,
        status="Alumni",
        employment_status="Entrepreneur",
        services_offered="Printing, design, delivery coordination",
        products_supplied="Branded shirts, caps, banners",
        active=True,
    )
    owner_user = User(
        email="owner@example.com",
        name="Owner User",
        password_hash="hashed",
        member=owner_member,
    )
    responder_user = User(
        email="supplier@example.com",
        name="Supplier User",
        password_hash="hashed",
        member=responder_member,
    )
    db_session.add_all([university, owner_member, responder_member, owner_user, responder_user])
    db_session.commit()

    created_listing = create_marketplace_listing(
        MarketplaceListingCreate(
            listing_type="need",
            title="Need congress shirts and caps",
            description="Looking for a supplier who can handle branded merchandise quickly.",
        ),
        db=db_session,
        user=owner_user,
    )

    registered_interest = register_marketplace_interest(
        created_listing.id,
        MarketplaceInterestCreate(note="I can supply shirts, caps, and banners within one week."),
        db=db_session,
        user=responder_user,
    )

    assert registered_interest.responder_name == "Supplier User"
    assert registered_interest.products_supplied == "Branded shirts, caps, banners"

    responder_view = list_marketplace_listings(db=db_session, user=responder_user)
    responder_listing = next(item for item in responder_view if item.id == created_listing.id)
    assert responder_listing.interest_registered is True
    assert responder_listing.interest_note == "I can supply shirts, caps, and banners within one week."
    assert responder_listing.response_count == 1

    owner_interests = list_marketplace_interests(created_listing.id, db=db_session, user=owner_user)
    assert len(owner_interests) == 1
    assert owner_interests[0].responder_name == "Supplier User"
    assert owner_interests[0].services_offered == "Printing, design, delivery coordination"
    assert owner_interests[0].products_supplied == "Branded shirts, caps, banners"

    with pytest.raises(HTTPException) as owner_register_exc:
        register_marketplace_interest(
            created_listing.id,
            MarketplaceInterestCreate(note="I own this listing."),
            db=db_session,
            user=owner_user,
        )

    assert owner_register_exc.value.status_code == 400

    with pytest.raises(HTTPException) as response_visibility_exc:
        list_marketplace_interests(created_listing.id, db=db_session, user=responder_user)

    assert response_visibility_exc.value.status_code == 403

    withdraw_marketplace_interest(created_listing.id, db=db_session, user=responder_user)
    owner_view_after_withdraw = list_marketplace_listings(db=db_session, user=owner_user)
    owner_listing_after_withdraw = next(item for item in owner_view_after_withdraw if item.id == created_listing.id)
    assert owner_listing_after_withdraw.response_count == 0
