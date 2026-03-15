import sys
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import seed as seed_module
from app.core.seed import DEFAULT_ROLES, REPORTING_PERIOD_SPECS
from app.core.zimbabwe_academic_catalog import ZIMBABWE_ACADEMIC_INSTITUTION_SPECS
from app.db.base import Base
from app.models import (
    AcademicProgram,
    CampusEvent,
    FundingRecord,
    MarketplaceListing,
    MandatoryProgram,
    Member,
    Program,
    ProgramBroadcast,
    ProgramUpdate,
    ReportingPeriod,
    Role,
    University,
    User,
)


def test_seed_data_bootstraps_reference_catalog_and_marketplace_fixture_accounts():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        with patch.object(seed_module, "hash_password", side_effect=lambda value: f"hashed::{value}"):
            seed_module.seed_data(db)

        assert db.query(Role).count() == len(DEFAULT_ROLES)
        assert db.query(User).count() >= 3
        assert db.query(University).count() == len(ZIMBABWE_ACADEMIC_INSTITUTION_SPECS)
        assert db.query(AcademicProgram).count() > 0
        assert db.query(ReportingPeriod).count() == len(REPORTING_PERIOD_SPECS)
        assert db.query(MandatoryProgram).count() > 0

        assert db.query(Member).count() == 0
        assert db.query(Program).count() == 0
        assert db.query(ProgramUpdate).count() == 0
        assert db.query(FundingRecord).count() == 0
        assert db.query(CampusEvent).count() == 0
        assert db.query(ProgramBroadcast).count() == 0
        assert db.query(MarketplaceListing).count() > 0
        assert len({listing.user_id for listing in db.query(MarketplaceListing).all()}) > 1
