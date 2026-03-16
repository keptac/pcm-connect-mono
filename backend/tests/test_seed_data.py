import sys
from pathlib import Path
from unittest.mock import patch
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import seed as seed_module
from app.core.seed import DEFAULT_ROLES, LEGACY_MANDATORY_EVENT_NAMES, MANDATORY_EVENT_SPECS, REPORTING_PERIOD_SPECS
from app.core.zimbabwe_academic_catalog import ZIMBABWE_ACADEMIC_INSTITUTION_SPECS
from app.db.base import Base
from app.models import (
    AcademicProgram,
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


def test_seed_data_bootstraps_reference_catalog_and_marketplace_fixtures():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        with patch.object(seed_module, "hash_password", side_effect=lambda value: f"hashed::{value}"):
            seed_module.seed_data(db)

        assert db.query(Role).count() == len(DEFAULT_ROLES)
        assert db.query(User).count() >= 2
        assert db.query(Union).count() >= 3
        assert db.query(University).count() == len(ZIMBABWE_ACADEMIC_INSTITUTION_SPECS)
        assert db.query(AcademicProgram).count() > 0
        assert db.query(ReportingPeriod).count() == len(REPORTING_PERIOD_SPECS)
        assert {
            item.code: (item.label, item.start_date, item.end_date)
            for item in db.query(ReportingPeriod).order_by(ReportingPeriod.sort_order.asc()).all()
        } == {
            "2026-S1": ("2026 Semester 1", date(2026, 1, 1), date(2026, 6, 30)),
            "2026-S2": ("2026 Semester 2", date(2026, 7, 1), date(2026, 12, 31)),
        }
        assert db.query(MandatoryProgram).count() > 0
        mandatory_event_names = {item.name for item in db.query(MandatoryProgram).all()}
        assert {item["name"] for item in MANDATORY_EVENT_SPECS}.issubset(mandatory_event_names)
        assert not set(LEGACY_MANDATORY_EVENT_NAMES).intersection(mandatory_event_names)

        assert db.query(Member).count() == 0
        assert db.query(Program).count() == 0
        assert db.query(ProgramUpdate).count() == 0
        assert db.query(FundingRecord).count() == 0
        assert db.query(CampusEvent).count() == 0
        assert db.query(ProgramBroadcast).count() == 0
        assert db.query(MarketplaceListing).count() > 0
        assert len({listing.user_id for listing in db.query(MarketplaceListing).all()}) == 1
        assert {
            "Zimbabwe Central Union Conference",
            "Zimbabwe East Union Conference",
            "Zimbabwe West Union Conference",
        }.issubset({item.name for item in db.query(Union).all()})
        assert {
            item.name: item.union.name if item.union else None
            for item in db.query(Conference).all()
        } == {
            "North Zimbabwe Conference": "Zimbabwe East Union Conference",
            "East Zimbabwe Conference": "Zimbabwe East Union Conference",
            "South Zimbabwe Conference": "Zimbabwe West Union Conference",
            "Central Zimbabwe Conference": "Zimbabwe Central Union Conference",
        }
        assert db.query(User).filter(User.email.in_([
            "marketplace.supplier@pcm.local",
            "marketplace.coordinator@pcm.local",
        ])).count() == 0

        recovery_account = db.query(User).filter(User.email == "adam@pcm.service").first()
        assert recovery_account is not None
        assert recovery_account.name == "PCM Recovery Service"
        assert recovery_account.is_active is True
        assert recovery_account.subject_to_tenure is False
        recovery_role_names = [
            role.name
            for role in db.query(Role).join(UserRole, UserRole.role_id == Role.id).filter(UserRole.user_id == recovery_account.id).all()
        ]
        assert recovery_role_names == ["service_recovery"]
