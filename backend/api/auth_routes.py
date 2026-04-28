"""
Auth API routes — register and login for returning users.

POST /auth/register  — create account with password
POST /auth/login     — login by email + password
"""

import logging
from fastapi import APIRouter, Depends, HTTPException # type: ignore
from pydantic import BaseModel # type: ignore
from sqlalchemy.orm import Session # type: ignore
from passlib.context import CryptContext # type: ignore

from database.db import get_db
from memory.learner_profile import (
    create_user,
    create_learner_profile,
    get_user_by_email,
    get_user_by_username,
    get_all_profiles_for_user,
)
from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# bcrypt password hashing
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(password: str) -> str:
    return _pwd_ctx.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def _profile_summary(profiles) -> list[dict]:
    return [
        {
            "profile_id": p.id,
            "target_language": p.target_language,
            "overall_level": p.overall_level,
            "sessions_completed": p.sessions_completed,
        }
        for p in profiles
    ]


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    native_language: str = "english"
    target_language: str
    learning_goal: str = "conversational"


class LoginRequest(BaseModel):
    email: str
    password: str


class UsernameLoginRequest(BaseModel):
    username: str



# Routes 

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new account with a password.
    Also creates a learner profile for the chosen target language.
    """
    if req.target_language.lower() not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{req.target_language}' not supported."
        )

    if get_user_by_email(db, req.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if get_user_by_username(db, req.username):
        raise HTTPException(status_code=409, detail="This username is already taken.")

    try:
        user = create_user(
            db=db,
            username=req.username,
            email=req.email,
            native_language=req.native_language.lower(),
            password_hash=_hash(req.password),
        )
        profile = create_learner_profile(
            db=db,
            user_id=user.id,
            target_language=req.target_language.lower(),
            learning_goal=req.learning_goal,
            initial_level="A1",
        )
        logger.info(f"Registered new user: {req.username}")
        return {
            "success": True,
            "user_id": user.id,
            "profile_id": profile.id,
            "username": user.username,
            "target_language": profile.target_language,
            "needs_assessment": False,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email + password.
    Returns user info and all their learner profiles.
    """
    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=401, detail="No account found with that email address.")

    if user.password_hash:
        if not _verify(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect password.")

    profiles = get_all_profiles_for_user(db, user.id)
    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "native_language": user.native_language,
        "profiles": _profile_summary(profiles),
    }


@router.post("/login/username")
def login_by_username(req: UsernameLoginRequest, db: Session = Depends(get_db)):
    """
    Passwordless login by username — for accounts created via onboarding
    before auth was added. Returns user + profiles so the frontend can
    restore the session.
    """
    user = get_user_by_username(db, req.username)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that username.")

    profiles = get_all_profiles_for_user(db, user.id)
    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "native_language": user.native_language,
        "profiles": _profile_summary(profiles),
    }
