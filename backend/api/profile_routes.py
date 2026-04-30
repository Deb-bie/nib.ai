"""
Profile API routes.

POST /profile/create         — create a new user + learner profile
POST /profile/assessment/start    — start placement assessment
POST /profile/assessment/message  — send message during assessment
GET  /profile/{profile_id}   — get full learner state
GET  /profile/{profile_id}/dashboard  — get dashboard data
GET  /profile/languages      — list supported languages
"""

from fastapi import APIRouter, Depends, HTTPException # type: ignore
from pydantic import BaseModel # type: ignore
from sqlalchemy.orm import Session # type: ignore

from database.db import get_db
from agent.orchestrator import Orchestrator
from config import SUPPORTED_LANGUAGES

router = APIRouter(prefix="/profile", tags=["Profile"])


# Request Models

class CreateUserRequest(BaseModel):
    username: str
    email: str
    native_language: str = "english"
    target_language: str
    learning_goal: str = "conversational"

class AssessmentMessageRequest(BaseModel):
    profile_id: int
    message: str

class AddLanguageRequest(BaseModel):
    user_id: int
    target_language: str
    learning_goal: str = "conversational"


# Routes

@router.post("/create")
def create_user(req: CreateUserRequest, db: Session = Depends(get_db)):
    try:
        result = Orchestrator.create_new_user(
            db=db,
            username=req.username,
            email=req.email,
            native_language=req.native_language.lower(),
            target_language=req.target_language.lower(),
            learning_goal=req.learning_goal,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create user: {str(e)}")


@router.post("/assessment/start")
def start_assessment(profile_id: int, db: Session = Depends(get_db)):
    try:
        orch = Orchestrator(db, profile_id)
        opening = orch.start_assessment()
        return {"success": True, "opening_message": opening}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/assessment/message")
def send_assessment_message(req: AssessmentMessageRequest, db: Session = Depends(get_db)):
    try:
        orch = Orchestrator(db, req.profile_id)
        result = orch.send_assessment_message(req.message)
        return {"success": True, **result}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    from memory.learner_profile import get_full_learner_state
    try:
        state = get_full_learner_state(db, profile_id)
        return {"success": True, "profile": state}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{profile_id}/dashboard")
def get_dashboard(profile_id: int, db: Session = Depends(get_db)):
    try:
        orch = Orchestrator(db, profile_id)
        data = orch.get_dashboard_data()
        return {"success": True, **data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/add-language")
def add_language(req: AddLanguageRequest, db: Session = Depends(get_db)):
    """
    Add a new target language profile for an existing user.
    Returns the new profile so the frontend can switch to it immediately.
    """
    from memory.learner_profile import get_user_by_id, create_learner_profile, get_learner_profiles_for_user
    try:
        if req.target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"'{req.target_language}' is not supported. Choose from: {list(SUPPORTED_LANGUAGES.keys())}"
            )
        user = get_user_by_id(db, req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = create_learner_profile(
            db=db,
            user_id=req.user_id,
            target_language=req.target_language.lower(),
            learning_goal=req.learning_goal,
            initial_level="A1",
        )
        # Return all profiles so the frontend can refresh its list
        all_profiles = get_learner_profiles_for_user(db, req.user_id)
        return {
            "success": True,
            "profile_id": profile.id,
            "target_language": profile.target_language,
            "overall_level": "A1",
            "needs_assessment": False,
            "all_profiles": [
                {
                    "profile_id": p.id,
                    "target_language": p.target_language,
                    "overall_level": p.overall_level or "A1",
                }
                for p in all_profiles
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not add language: {str(e)}")


@router.get("/languages/supported")
def get_supported_languages():
    return {
        "languages": [
            {
                "key": key,
                "name": info["name"],
                "native_name": info["native_name"],
                "code": info["code"],
            }
            for key, info in SUPPORTED_LANGUAGES.items()
        ]
    }
