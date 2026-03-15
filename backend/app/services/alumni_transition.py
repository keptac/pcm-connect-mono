from datetime import date
from sqlalchemy.orm import Session
from ..models import Member, MembershipStatusHistory


def run_transition(db: Session, actor_user_id: int | None = None) -> int:
    today = date.today()
    members = db.query(Member).filter(Member.expected_graduation_date.isnot(None)).all()
    updated = 0
    for member in members:
        if member.status == "Student" and member.expected_graduation_date and member.expected_graduation_date < today:
            history = MembershipStatusHistory(
                member_id=member.id,
                old_status=member.status,
                new_status="Alumni",
                changed_by_user_id=actor_user_id,
                reason="Program end date passed",
            )
            member.status = "Alumni"
            updated += 1
            db.add(history)
    db.commit()
    return updated
