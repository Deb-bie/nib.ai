"""
Progress API routes.

GET /progress/{profile_id}/errors      — error history and patterns
GET /progress/{profile_id}/skills      — skill level breakdown
GET /progress/{profile_id}/vocabulary  — vocabulary and SR stats
GET /progress/{profile_id}/plan        — current curriculum plan + agent reasoning
"""

from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore

from database.db import get_db
from memory.error_tracker import get_error_summary, get_recurring_errors
from memory.learner_profile import (
    get_skill_summary,
    get_current_curriculum_plan,
    get_learner_profile_by_id,
)
from memory.spaced_repetition import get_vocabulary_stats, get_due_items_summary

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("/{profile_id}/errors")
def get_errors(profile_id: int, db: Session = Depends(get_db)):
    summary = get_error_summary(db, profile_id)
    return {"success": True, **summary}


@router.get("/{profile_id}/skills")
def get_skills(profile_id: int, db: Session = Depends(get_db)):
    profile = get_learner_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    skills = get_skill_summary(db, profile_id)
    return {
        "success": True,
        "overall_level": profile.overall_level,
        "skills": skills,
    }


@router.get("/{profile_id}/vocabulary")
def get_vocabulary(profile_id: int, db: Session = Depends(get_db)):
    stats = get_vocabulary_stats(db, profile_id)
    due = get_due_items_summary(db, profile_id)
    return {"success": True, "stats": stats, "due_today": due}


@router.get("/{profile_id}/plan")
def get_current_plan(profile_id: int, db: Session = Depends(get_db)):
    """
    Returns the agent's current curriculum plan including its reasoning.
    """
    plan = get_current_curriculum_plan(db, profile_id)
    if not plan:
        return {"success": True, "plan": None, "message": "No plan yet — complete an assessment first."}
    return {
        "success": True,
        "plan": {
            "session_focus": plan.session_focus,
            "priority_concepts": plan.priority_concepts,
            "review_items": plan.review_items,
            "agent_reasoning": plan.agent_reasoning,
            "detected_issues": plan.detected_issues,
            "strategy_overrides": plan.strategy_overrides,
            "created_at": plan.created_at.isoformat(),
        },
    }
