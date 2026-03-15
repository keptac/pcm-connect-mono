from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models import University, Member
from app.services.alumni_transition import run_transition


def test_transition_updates_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        uni = University(name="Test Uni")
        db.add(uni)
        db.commit()
        db.refresh(uni)
        member = Member(
            university_id=uni.id,
            first_name="A",
            last_name="B",
            expected_graduation_date=date.today() - timedelta(days=1),
            status="Student",
        )
        db.add(member)
        db.commit()
        updated = run_transition(db, None)
        assert updated == 1
