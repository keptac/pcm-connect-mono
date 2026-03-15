from pydantic import BaseModel

from .common import UserRead


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GeneralUserLookupRequest(BaseModel):
    last_name: str
    university_id: int
    start_year: int


class GeneralUserMatchRead(BaseModel):
    member_id: str
    member_number: str | None = None
    first_name: str
    last_name: str
    university_id: int
    university_name: str | None = None
    start_year: int | None = None
    status: str
    program_of_study_name: str | None = None
    email_hint: str | None = None


class GeneralUserRegisterRequest(BaseModel):
    member_id: str
    email: str
    password: str
    donor_interest: bool = False


class AuthSession(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
    sign_in_identifier: str
