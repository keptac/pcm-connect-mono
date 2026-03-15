from datetime import datetime
from typing import List, Optional

from .common import SchemaModel


class DashboardOverview(SchemaModel):
    active_universities: int
    active_programs: int
    active_people: int
    students_count: int
    staff_count: int
    alumni_count: int
    people_served: int
    updates_logged: int
    scheduled_events: int
    upcoming_events: int
    income_total: float
    expense_total: float
    net_total: float


class GroupedStats(SchemaModel):
    label: str
    count: int


class GroupedAmount(SchemaModel):
    label: str
    amount: float


class UniversityPerformance(SchemaModel):
    university_id: int
    university_name: str
    active_members: int
    active_programs: int
    people_served: int
    funding_total: float
    latest_update_at: Optional[datetime] = None


class ProgramPerformance(SchemaModel):
    program_id: int
    program_name: str
    university_name: str
    category: Optional[str] = None
    manager_name: Optional[str] = None
    status: Optional[str] = None
    beneficiaries_served: int
    annual_budget: Optional[float] = None
    last_update_at: Optional[datetime] = None
    update_count: int


class FundingBreakdown(SchemaModel):
    income_total: float
    expense_total: float
    net_total: float
    by_type: List[GroupedAmount]
    by_university: List[GroupedAmount]
