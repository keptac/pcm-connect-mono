from collections import defaultdict
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import FundingRecord, Member, Program, ProgramUpdate, University


def _is_expense(entry_type: str | None) -> bool:
    return (entry_type or "").lower() == "expense"


def _funding_direction(record: FundingRecord) -> str:
    return (record.flow_direction or ("outflow" if _is_expense(record.entry_type) else "inflow")).lower()


def _funding_category(record: FundingRecord) -> str:
    if record.receipt_category:
        return record.receipt_category
    normalized = (record.entry_type or "").lower()
    if normalized == "donation":
        return "Donation"
    if normalized == "zunde":
        return "Zunde"
    if normalized == "offering":
        return "Offering"
    if normalized in {"subscription", "subscriptions"}:
        return "Subscriptions"
    return "Other"


def _scoped_query(query, model, university_id: int | None):
    if not university_id:
        return query
    return query.filter(model.university_id == university_id)


def _scoped_program_query(db: Session, university_id: int | None):
    query = db.query(Program)
    if university_id:
        query = query.filter(or_(Program.university_id == university_id, Program.university_id.is_(None)))
    return query


def dashboard_overview(db: Session, university_id: int | None = None):
    universities_query = db.query(University).filter(University.is_active.is_(True))
    if university_id:
        universities_query = universities_query.filter(University.id == university_id)

    programs = _scoped_program_query(db, university_id).all()
    members = _scoped_query(db.query(Member), Member, university_id).all()
    updates_query = _scoped_query(db.query(ProgramUpdate), ProgramUpdate, university_id)
    funding = _scoped_query(db.query(FundingRecord), FundingRecord, university_id).all()
    income_total = sum(item.amount for item in funding if _funding_direction(item) != "outflow")
    expense_total = sum(item.amount for item in funding if _funding_direction(item) == "outflow")
    now = datetime.utcnow()
    today = now.date()
    dated_programs = [program for program in programs if program.start_date]

    return {
        "active_universities": universities_query.count(),
        "active_programs": len([program for program in programs if (program.status or "active") != "archived"]),
        "active_people": len([member for member in members if member.active]),
        "students_count": len([member for member in members if (member.status or "").lower() == "student"]),
        "staff_count": len([member for member in members if (member.status or "").lower() == "staff"]),
        "alumni_count": len([member for member in members if (member.status or "").lower() == "alumni"]),
        "people_served": sum(program.beneficiaries_served or 0 for program in programs),
        "updates_logged": updates_query.count(),
        "scheduled_events": len(dated_programs),
        "upcoming_events": len(
            [
                program
                for program in dated_programs
                if (program.end_date or program.start_date) >= today and (program.status or "active").lower() != "archived"
            ]
        ),
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": income_total - expense_total,
    }


def university_performance(db: Session, university_id: int | None = None):
    universities_query = db.query(University).filter(University.is_active.is_(True))
    if university_id:
        universities_query = universities_query.filter(University.id == university_id)

    items = []
    for university in universities_query.order_by(University.name.asc()).all():
        active_members = len([member for member in university.members if member.active])
        active_programs = len(
            [program for program in university.programs if (program.status or "active") != "archived"]
        )
        funding_total = 0.0
        for record in university.funding_records:
            funding_total += -record.amount if _funding_direction(record) == "outflow" else record.amount

        latest_update = max(
            (update.created_at for update in university.program_updates),
            default=None,
        )
        items.append(
            {
                "university_id": university.id,
                "university_name": university.name,
                "active_members": active_members,
                "active_programs": active_programs,
                "people_served": sum(program.beneficiaries_served or 0 for program in university.programs),
                "funding_total": funding_total,
                "latest_update_at": latest_update,
            }
        )
    return items


def program_performance(db: Session, university_id: int | None = None):
    programs_query = _scoped_program_query(db, university_id).order_by(Program.name.asc())

    results = []
    for program in programs_query.all():
        results.append(
            {
                "program_id": program.id,
                "program_name": program.name,
                "university_name": program.university.name if program.university else "All universities and campuses",
                "category": program.category,
                "manager_name": program.manager_name,
                "status": program.status,
                "beneficiaries_served": program.beneficiaries_served or 0,
                "annual_budget": program.annual_budget,
                "last_update_at": program.last_update_at,
                "update_count": len(program.updates),
            }
        )
    return results


def funding_breakdown(db: Session, university_id: int | None = None):
    funding = _scoped_query(db.query(FundingRecord), FundingRecord, university_id).all()

    income_total = sum(item.amount for item in funding if _funding_direction(item) != "outflow")
    expense_total = sum(item.amount for item in funding if _funding_direction(item) == "outflow")

    by_type = defaultdict(float)
    by_university = defaultdict(float)

    for item in funding:
        direction = _funding_direction(item)
        category = _funding_category(item)
        by_type[f"{direction.title()} / {category}"] += item.amount
        label = item.university.name if item.university else "PCM Office / National Office"
        by_university[label] += -item.amount if direction == "outflow" else item.amount

    return {
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": income_total - expense_total,
        "by_type": [{"label": label, "amount": amount} for label, amount in sorted(by_type.items())],
        "by_university": [
            {"label": label, "amount": amount}
            for label, amount in sorted(by_university.items(), key=lambda item: item[0])
        ],
    }


def member_breakdown(db: Session, group_by: str, university_id: int | None = None):
    members = _scoped_query(db.query(Member), Member, university_id).all()
    counts = defaultdict(int)

    for member in members:
        if group_by == "program":
            label = member.program_of_study.name if member.program_of_study else "Unassigned"
        elif group_by == "university":
            label = member.university.name if member.university else "Unassigned"
        else:
            label = member.status or "Unknown"
        counts[label] += 1

    return [{"label": label, "count": count} for label, count in sorted(counts.items())]
