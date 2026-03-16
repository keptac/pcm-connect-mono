from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UniversityBase(SchemaModel):
    name: str
    short_code: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    conference_id: Optional[int] = None
    mission_focus: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: bool = True


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(SchemaModel):
    name: Optional[str] = None
    short_code: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    conference_id: Optional[int] = None
    mission_focus: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: Optional[bool] = None


class UniversityRead(UniversityBase):
    id: int
    conference_name: Optional[str] = None
    union_name: Optional[str] = None
    created_at: datetime
    program_count: int = 0
    member_count: int = 0


class ConferenceBase(SchemaModel):
    name: str
    union_name: str
    is_active: bool = True


class ConferenceCreate(ConferenceBase):
    pass


class ConferenceUpdate(SchemaModel):
    name: Optional[str] = None
    union_name: Optional[str] = None
    is_active: Optional[bool] = None


class ConferenceRead(ConferenceBase):
    id: int
    campus_count: int = 0
    created_at: datetime


class ProgramBase(SchemaModel):
    university_id: Optional[int] = None
    name: str
    category: Optional[str] = None
    status: Optional[str] = "active"
    description: Optional[str] = None
    audience: Optional[str] = "Students"
    manager_name: Optional[str] = None
    target_beneficiaries: Optional[int] = None
    beneficiaries_served: Optional[int] = 0
    annual_budget: Optional[float] = None
    duration_weeks: Optional[float] = None
    level: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdatePayload(SchemaModel):
    university_id: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    audience: Optional[str] = None
    manager_name: Optional[str] = None
    target_beneficiaries: Optional[int] = None
    beneficiaries_served: Optional[int] = None
    annual_budget: Optional[float] = None
    duration_weeks: Optional[float] = None
    level: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProgramRead(ProgramBase):
    id: int
    university_name: Optional[str] = None
    last_update_at: Optional[datetime] = None
    update_count: int = 0


class AcademicProgramBase(SchemaModel):
    university_id: int
    name: str
    faculty: Optional[str] = None
    study_area: Optional[str] = None
    qualification_level: Optional[str] = None
    is_active: bool = True


class AcademicProgramRead(AcademicProgramBase):
    id: int
    university_name: Optional[str] = None
    created_at: datetime


class UserCreate(SchemaModel):
    email: str
    name: Optional[str] = None
    password: str
    university_id: Optional[int] = None
    roles: List[str] = Field(default_factory=list)
    force_password_reset: bool = False
    tenure_months: int = 24
    tenure_starts_on: Optional[date] = None


class UserUpdate(SchemaModel):
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None
    university_id: Optional[int] = None
    roles: Optional[List[str]] = None
    force_password_reset: Optional[bool] = None
    tenure_months: Optional[int] = None
    tenure_starts_on: Optional[date] = None
    is_active: Optional[bool] = None


class UserPasswordRecovery(SchemaModel):
    new_password: str
    force_password_reset: bool = True


class UserRead(SchemaModel):
    id: int
    email: str
    name: Optional[str] = None
    university_id: Optional[int] = None
    university_name: Optional[str] = None
    member_id: Optional[str] = None
    member_number: Optional[str] = None
    member_status: Optional[str] = None
    member_university_id: Optional[int] = None
    member_university_name: Optional[str] = None
    donor_interest: bool = False
    is_active: bool
    is_system_admin: bool = False
    subject_to_tenure: bool = False
    force_password_reset: bool = False
    tenure_months: Optional[int] = None
    tenure_starts_on: Optional[date] = None
    tenure_ends_on: Optional[date] = None
    disabled_at: Optional[datetime] = None
    deletion_due_at: Optional[date] = None
    roles: List[str]


class MemberBase(SchemaModel):
    member_id: Optional[str] = None
    first_name: str
    last_name: str
    gender: Optional[str] = None
    dob: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    university_id: int
    program_of_study_id: Optional[int] = None
    start_year: Optional[int] = None
    expected_graduation_date: Optional[date] = None
    intake: Optional[str] = None
    status: Optional[str] = "Student"
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    current_city: Optional[str] = None
    services_offered: Optional[str] = None
    products_supplied: Optional[str] = None
    active: Optional[bool] = True


class MemberCreate(MemberBase):
    pass


class MemberUpdate(SchemaModel):
    member_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    university_id: Optional[int] = None
    program_of_study_id: Optional[int] = None
    start_year: Optional[int] = None
    expected_graduation_date: Optional[date] = None
    intake: Optional[str] = None
    status: Optional[str] = None
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    current_city: Optional[str] = None
    services_offered: Optional[str] = None
    products_supplied: Optional[str] = None
    active: Optional[bool] = None


class MemberSelfProfileUpdate(SchemaModel):
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    current_city: Optional[str] = None
    services_offered: Optional[str] = None
    products_supplied: Optional[str] = None


class MemberRead(MemberBase):
    id: str
    program_of_study_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AlumniConnectRead(SchemaModel):
    id: str
    member_id: Optional[str] = None
    first_name: str
    last_name: str
    university_id: int
    university_name: Optional[str] = None
    program_of_study_name: Optional[str] = None
    expected_graduation_date: Optional[date] = None
    start_year: Optional[int] = None
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    current_city: Optional[str] = None
    services_offered: Optional[str] = None
    products_supplied: Optional[str] = None
    email: Optional[str] = None


class UpdateAttachmentRead(SchemaModel):
    name: str
    stored_name: str
    url: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    category: Optional[str] = None
    meeting_date: Optional[date] = None
    venue: Optional[str] = None
    notes: Optional[str] = None


class ProgramImpactUpdateBase(SchemaModel):
    university_id: int
    program_id: Optional[int] = None
    title: Optional[str] = None
    event_name: str
    event_detail: Optional[str] = None
    reporting_period: str
    summary: str
    outcomes: Optional[str] = None
    challenges: Optional[str] = None
    next_steps: Optional[str] = None
    beneficiaries_reached: int = 0
    volunteers_involved: int = 0
    funds_used: Optional[float] = None


class ProgramImpactUpdateCreate(ProgramImpactUpdateBase):
    pass


class ProgramImpactUpdatePatch(SchemaModel):
    university_id: Optional[int] = None
    program_id: Optional[int] = None
    title: Optional[str] = None
    event_name: Optional[str] = None
    event_detail: Optional[str] = None
    reporting_period: Optional[str] = None
    summary: Optional[str] = None
    outcomes: Optional[str] = None
    challenges: Optional[str] = None
    next_steps: Optional[str] = None
    beneficiaries_reached: Optional[int] = None
    volunteers_involved: Optional[int] = None
    funds_used: Optional[float] = None


class ProgramImpactUpdateRead(ProgramImpactUpdateBase):
    id: int
    program_name: Optional[str] = None
    university_name: Optional[str] = None
    attachments: List[UpdateAttachmentRead] = Field(default_factory=list)
    submitted_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MandatoryProgramBase(SchemaModel):
    name: str
    program_type: str = "event"
    allow_other_detail: bool = False
    is_active: bool = True
    sort_order: int = 0


class MandatoryProgramCreate(MandatoryProgramBase):
    pass


class MandatoryProgramUpdate(SchemaModel):
    name: Optional[str] = None
    program_type: Optional[str] = None
    allow_other_detail: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class MandatoryProgramRead(MandatoryProgramBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ReportingPeriodBase(SchemaModel):
    code: str
    label: str
    start_date: date
    end_date: date
    is_active: bool = True
    sort_order: int = 0


class ReportingPeriodCreate(ReportingPeriodBase):
    pass


class ReportingPeriodUpdate(SchemaModel):
    code: Optional[str] = None
    label: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ReportingPeriodRead(ReportingPeriodBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CampusEventBase(SchemaModel):
    university_id: int
    program_id: Optional[int] = None
    title: str
    event_type: Optional[str] = None
    audience: Optional[str] = None
    status: Optional[str] = "scheduled"
    venue: Optional[str] = None
    description: Optional[str] = None
    organizer_name: Optional[str] = None
    starts_at: datetime
    ends_at: datetime


class CampusEventCreate(CampusEventBase):
    pass


class CampusEventUpdate(SchemaModel):
    university_id: Optional[int] = None
    program_id: Optional[int] = None
    title: Optional[str] = None
    event_type: Optional[str] = None
    audience: Optional[str] = None
    status: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    organizer_name: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class CampusEventRead(CampusEventBase):
    id: int
    university_name: Optional[str] = None
    program_name: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class BroadcastInviteRead(SchemaModel):
    id: int
    university_id: int
    university_name: Optional[str] = None
    status: str
    note: Optional[str] = None
    responded_at: Optional[datetime] = None


class ProgramBroadcastBase(SchemaModel):
    university_id: int
    program_id: Optional[int] = None
    title: str
    summary: str
    venue: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    visibility: Optional[str] = "network"
    status: Optional[str] = "open"
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class ProgramBroadcastCreate(ProgramBroadcastBase):
    invited_university_ids: List[int] = Field(default_factory=list)


class ProgramBroadcastUpdate(SchemaModel):
    university_id: Optional[int] = None
    program_id: Optional[int] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    venue: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    invited_university_ids: Optional[List[int]] = None


class BroadcastInviteUpdate(SchemaModel):
    status: str
    note: Optional[str] = None


class ProgramBroadcastRead(ProgramBroadcastBase):
    id: int
    university_name: Optional[str] = None
    program_name: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    invites: List[BroadcastInviteRead] = Field(default_factory=list)
    my_invite_status: Optional[str] = None


class ChatContactRead(SchemaModel):
    id: int
    email: str
    name: Optional[str] = None
    university_id: Optional[int] = None
    university_name: Optional[str] = None
    member_id: Optional[str] = None
    member_number: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    chat_public_key: Optional[str] = None


class ChatKeyBundleRead(SchemaModel):
    public_key: Optional[str] = None
    private_key_encrypted: Optional[str] = None
    key_salt: Optional[str] = None
    key_iv: Optional[str] = None
    key_algorithm: Optional[str] = None


class ChatKeyBundleUpdate(SchemaModel):
    public_key: str
    private_key_encrypted: str
    key_salt: str
    key_iv: str
    key_algorithm: str = "PBKDF2-AES-GCM"


class ChatConversationCreate(SchemaModel):
    recipient_user_id: int


class ChatMessageCreate(SchemaModel):
    body: Optional[str] = None
    ciphertext: Optional[str] = None
    iv: Optional[str] = None
    algorithm: Optional[str] = "AES-GCM"
    key_envelopes: Dict[str, str] = Field(default_factory=dict)


class ChatMessageRead(SchemaModel):
    id: int
    thread_id: int
    sender_user_id: int
    sender_name: Optional[str] = None
    sender_university_name: Optional[str] = None
    body: Optional[str] = None
    ciphertext: Optional[str] = None
    iv: Optional[str] = None
    algorithm: Optional[str] = None
    key_envelopes: Dict[str, str] = Field(default_factory=dict)
    is_encrypted: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class ChatConversationRead(SchemaModel):
    id: int
    participants: List[ChatContactRead] = Field(default_factory=list)
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0


class FundingRecordBase(SchemaModel):
    university_id: Optional[int] = None
    program_id: Optional[int] = None
    source_name: str
    entry_type: str = "donation"
    flow_direction: Optional[str] = "inflow"
    receipt_category: Optional[str] = None
    category_detail: Optional[str] = None
    reporting_window: Optional[str] = "monthly"
    amount: float
    currency: str = "USD"
    transaction_date: date
    channel: Optional[str] = None
    designation: Optional[str] = None
    notes: Optional[str] = None


class FundingRecordCreate(FundingRecordBase):
    pass


class FundingRecordPatch(SchemaModel):
    university_id: Optional[int] = None
    program_id: Optional[int] = None
    source_name: Optional[str] = None
    entry_type: Optional[str] = None
    flow_direction: Optional[str] = None
    receipt_category: Optional[str] = None
    category_detail: Optional[str] = None
    reporting_window: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    transaction_date: Optional[date] = None
    channel: Optional[str] = None
    designation: Optional[str] = None
    notes: Optional[str] = None


class FundingRecordRead(FundingRecordBase):
    id: int
    university_name: Optional[str] = None
    program_name: Optional[str] = None
    recorded_by: Optional[int] = None
    created_at: datetime


class ReportTemplateCreate(SchemaModel):
    name: str
    version: str
    columns: List[str]
    file_format: str = "csv"


class ReportTemplateRead(SchemaModel):
    id: int
    name: str
    version: str
    columns: List[str]
    file_format: str
    created_at: datetime


class UploadReportResponse(SchemaModel):
    id: int
    status: str
    original_filename: str


class UploadedReportRead(SchemaModel):
    id: int
    template_id: Optional[int] = None
    university_id: Optional[int] = None
    period_start: date
    period_end: date
    report_type: Optional[str] = None
    original_filename: str
    status: str
    uploaded_at: datetime


class ParsedRowRead(SchemaModel):
    id: int
    row_index: int
    data: Dict[str, Any]
    is_valid: bool
    validation_errors: Optional[List[str]] = None


class AuditLogRead(SchemaModel):
    id: int
    actor_user_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class MarketplaceListingBase(SchemaModel):
    listing_type: str
    title: str
    description: str
    category: Optional[str] = None
    price_text: Optional[str] = None


class MarketplaceListingCreate(MarketplaceListingBase):
    university_id: Optional[int] = None


class MarketplaceListingUpdate(SchemaModel):
    university_id: Optional[int] = None
    listing_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price_text: Optional[str] = None
    status: Optional[str] = None


class MarketplaceInterestCreate(SchemaModel):
    note: Optional[str] = None


class MarketplaceInterestRead(SchemaModel):
    id: int
    listing_id: int
    user_id: int
    responder_name: Optional[str] = None
    responder_email: str
    responder_member_id: Optional[str] = None
    responder_member_status: Optional[str] = None
    responder_university_name: Optional[str] = None
    responder_chat_ready: bool = False
    employment_status: Optional[str] = None
    services_offered: Optional[str] = None
    products_supplied: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MarketplaceListingRead(MarketplaceListingBase):
    id: int
    user_id: int
    university_id: Optional[int] = None
    university_name: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: str
    owner_member_id: Optional[str] = None
    owner_member_status: Optional[str] = None
    owner_chat_ready: bool = False
    response_count: int = 0
    interest_registered: bool = False
    interest_note: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class CondensedMissionReportRead(SchemaModel):
    reporting_period: str
    reporting_period_label: Optional[str] = None
    event_name: str
    update_count: int
    university_count: int
    total_beneficiaries_reached: int
    total_volunteers_involved: int
    total_funds_used: float
    latest_update_at: Optional[datetime] = None
    highlights: List[str] = Field(default_factory=list)
