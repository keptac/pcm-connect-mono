from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from ..db import get_session
from ..schemas import LoginRequest, Token
from ..services.auth import authenticate_user, create_access_token
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = authenticate_user(session, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.email, settings.access_token_exp_minutes)
    return Token(access_token=token)
