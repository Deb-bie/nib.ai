"""
Learner profile operations.

All reads and writes to the learner model go through here
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session # type: ignore

from database.models import (
    User, LearnerProfile, SkillLevel, CurriculumPlan
)
from config import SKILL_TYPES, CEFR_LEVELS


#  User
def create_user(
    db: Session,
    username: str,
    email: str,
    native_language: str = "english",
    password_hash: str | None = None,
) -> User:
    user = User(
        username=username,
        email=email,
        native_language=native_language,
        password_hash=password_hash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()



# Learner Profile 

def create_learner_profile(
    db: Session,
    user_id: int,
    target_language: str,
    learning_goal: str = "conversational",
    initial_level: str = "A1",
) -> LearnerProfile:
    """
    Create a new learner profile. overall_level starts at A1 (beginner).
    The level is updated automatically as the learner progresses through sessions.
    Called when a user starts learning a new language.
    """
    profile = LearnerProfile(
        user_id=user_id,
        target_language=target_language.lower(),
        overall_level=initial_level,
        learning_goal=learning_goal,
    )
    db.add(profile)
    db.flush() 

    for skill in SKILL_TYPES:
        skill_level = SkillLevel(
            learner_profile_id=profile.id,
            skill=skill,
            level="A1",
            score=0.0,
        )
        db.add(skill_level)

    db.commit()
    db.refresh(profile)
    return profile


def get_learner_profiles_for_user(db: Session, user_id: int) -> list[LearnerProfile]:
    """Return all active language profiles for a given user."""
    return (
        db.query(LearnerProfile)
        .filter(LearnerProfile.user_id == user_id, LearnerProfile.is_active)
        .order_by(LearnerProfile.id.asc())
        .all()
    )


def get_learner_profile(
    db: Session, user_id: int, target_language: str
) -> Optional[LearnerProfile]:
    return (
        db.query(LearnerProfile)
        .filter(
            LearnerProfile.user_id == user_id,
            LearnerProfile.target_language == target_language.lower(),
            LearnerProfile.is_active,
        )
        .first()
    )


def get_learner_profile_by_id(db: Session, profile_id: int) -> Optional[LearnerProfile]:
    return db.query(LearnerProfile).filter(LearnerProfile.id == profile_id).first()


def get_all_profiles_for_user(db: Session, user_id: int) -> list[LearnerProfile]:
    return (
        db.query(LearnerProfile)
        .filter(LearnerProfile.user_id == user_id, LearnerProfile.is_active)
        .all()
    )


def update_overall_level(db: Session, profile_id: int, new_level: str) -> LearnerProfile:
    profile = get_learner_profile_by_id(db, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")
    profile.overall_level = new_level
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


def update_preferred_style(db: Session, profile_id: int, style: str) -> LearnerProfile:
    profile = get_learner_profile_by_id(db, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")
    profile.preferred_style = style
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


def record_session_completed(db: Session, profile_id: int, duration_minutes: float) -> LearnerProfile:
    """Update streak, session count, and total minutes after a session ends."""
    profile = get_learner_profile_by_id(db, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    now = datetime.utcnow()
    profile.sessions_completed += 1
    profile.total_minutes_studied += int(duration_minutes)
    profile.last_session_at = now


    if profile.last_session_at:
        days_since = (now.date() - profile.last_session_at.date()).days
        if days_since <= 1:
            profile.streak_days += 1
        else:
            profile.streak_days = 1   # reset streak
    else:
        profile.streak_days = 1

    profile.updated_at = now
    db.commit()
    db.refresh(profile)
    return profile




# Skill Levels

def get_skill_levels(db: Session, profile_id: int) -> list[SkillLevel]:
    return db.query(SkillLevel).filter(SkillLevel.learner_profile_id == profile_id).all()


def get_skill_level(db: Session, profile_id: int, skill: str) -> Optional[SkillLevel]:
    return (
        db.query(SkillLevel)
        .filter(SkillLevel.learner_profile_id == profile_id, SkillLevel.skill == skill)
        .first()
    )


def update_skill_level(
    db: Session, profile_id: int, skill: str, score_delta: float
) -> SkillLevel:
    """
    Update a skill's score and promote to the next CEFR level if score >= 100.
    score_delta can be positive (correct) or negative (incorrect).
    """
    skill_level = get_skill_level(db, profile_id, skill)
    if not skill_level:
        raise ValueError(f"Skill {skill} not found for profile {profile_id}")

    skill_level.score = max(0.0, min(100.0, skill_level.score + score_delta))

 
    if skill_level.score >= 100.0:
        current_idx = CEFR_LEVELS.index(skill_level.level)
        if current_idx < len(CEFR_LEVELS) - 1:
            skill_level.level = CEFR_LEVELS[current_idx + 1]
            skill_level.score = 0.0  

    skill_level.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(skill_level)
    return skill_level


def get_skill_summary(db: Session, profile_id: int) -> dict:
    """Returns a clean dict of skill → {level, score} for the agent to read."""
    skills = get_skill_levels(db, profile_id)
    return {s.skill: {"level": s.level, "score": round(s.score, 1)} for s in skills}




# Curriculum Plan 

def get_current_curriculum_plan(db: Session, profile_id: int) -> Optional[CurriculumPlan]:
    return (
        db.query(CurriculumPlan)
        .filter(
            CurriculumPlan.learner_profile_id == profile_id,
            CurriculumPlan.is_current,
        )
        .order_by(CurriculumPlan.created_at.desc())
        .first()
    )


def save_curriculum_plan(
    db: Session,
    profile_id: int,
    session_focus: dict,
    priority_concepts: list,
    concepts_to_skip: list,
    review_items: list,
    agent_reasoning: str,
    detected_issues: list,
    strategy_overrides: dict,
) -> CurriculumPlan:
    """
    Deactivate the previous plan and save the new one.
    Called by the curriculum planner after every session.
    """

    db.query(CurriculumPlan).filter(
        CurriculumPlan.learner_profile_id == profile_id,
        CurriculumPlan.is_current,
    ).update({"is_current": False})

    plan = CurriculumPlan(
        learner_profile_id=profile_id,
        is_current=True,
        session_focus=session_focus,
        priority_concepts=priority_concepts,
        concepts_to_skip=concepts_to_skip,
        review_items=review_items,
        agent_reasoning=agent_reasoning,
        detected_issues=detected_issues,
        strategy_overrides=strategy_overrides,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_full_learner_state(db: Session, profile_id: int) -> dict:
    """
    Returns everything the agent needs to know about a learner
    """
    profile = get_learner_profile_by_id(db, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    skill_summary = get_skill_summary(db, profile_id)
    current_plan = get_current_curriculum_plan(db, profile_id)

    return {
        "profile_id": profile.id,
        "target_language": profile.target_language,
        "overall_level": profile.overall_level,
        "learning_goal": profile.learning_goal,
        "preferred_style": profile.preferred_style,
        "sessions_completed": profile.sessions_completed,
        "total_minutes_studied": profile.total_minutes_studied,
        "streak_days": profile.streak_days,
        "last_session_at": profile.last_session_at.isoformat() if profile.last_session_at else None,
        "skills": skill_summary,
        "current_plan": {
            "session_focus": current_plan.session_focus,
            "priority_concepts": current_plan.priority_concepts,
            "review_items": current_plan.review_items,
            "agent_reasoning": current_plan.agent_reasoning,
            "detected_issues": current_plan.detected_issues,
        } if current_plan else None,
    }