"""
Error tracker.

Logs every mistake the learner makes and detects recurring patterns.
When the same error concept appears MAX_ERRORS_BEFORE_STRATEGY_SWITCH times,
the agent is notified so it can switch teaching strategy.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session # type: ignore

from database.models import Error
from config import MAX_ERRORS_BEFORE_STRATEGY_SWITCH


# Log an Error

def log_error(
    db: Session,
    profile_id: int,
    session_id: int,
    category: str,
    concept: str,
    user_input: str,
    correct_form: str,
    explanation: str = "",
) -> Error:
    """
    Log a new error or increment occurrence count if already seen.
    Returns the error record — caller can check .strategy_switched to know
    if a strategy change was triggered.
    """
    # Check if this exact concept error already exists
    existing = (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.concept == concept,
            ~Error.resolved,
        )
        .first()
    )

    if existing:
        existing.occurrence_count += 1
        existing.last_seen_at = datetime.utcnow()
        existing.user_input = user_input
        existing.session_id = session_id

        # Trigger strategy switch if threshold hit
        if (
            existing.occurrence_count >= MAX_ERRORS_BEFORE_STRATEGY_SWITCH
            and not existing.strategy_switched
        ):
            existing.strategy_switched = True

        db.commit()
        db.refresh(existing)
        return existing

    # First time seeing this error
    error = Error(
        learner_profile_id=profile_id,
        session_id=session_id,
        category=category,
        concept=concept,
        user_input=user_input,
        correct_form=correct_form,
        explanation=explanation,
        occurrence_count=1,
        strategy_switched=False,
        resolved=False,
    )
    db.add(error)
    db.commit()
    db.refresh(error)
    return error


# Query Errors

def get_recurring_errors(db: Session, profile_id: int, min_occurrences: int = 2) -> list[Error]:
    """Returns errors that have occurred more than once — these are the priority targets."""
    return (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.occurrence_count >= min_occurrences,
            ~Error.resolved,
        )
        .order_by(Error.occurrence_count.desc())
        .all()
    )


def get_strategy_switch_errors(db: Session, profile_id: int) -> list[Error]:
    """Returns errors that have triggered a strategy switch — agent needs to act on these."""
    return (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.strategy_switched,
            ~Error.resolved,
        )
        .all()
    )


def get_errors_by_category(db: Session, profile_id: int, category: str) -> list[Error]:
    return (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.category == category,
            ~Error.resolved,
        )
        .order_by(Error.occurrence_count.desc())
        .all()
    )


def get_errors_for_session(db: Session, session_id: int) -> list[Error]:
    return db.query(Error).filter(Error.session_id == session_id).all()


def get_error_summary(db: Session, profile_id: int) -> dict:
    """
    Returns a structured summary of all unresolved errors for the agent.
    Format is designed to be passed directly into the LLM context.
    """
    errors = (
        db.query(Error)
        .filter(Error.learner_profile_id == profile_id, ~Error.resolved)
        .order_by(Error.occurrence_count.desc())
        .limit(20)
        .all()
    )

    return {
        "total_unresolved": len(errors),
        "recurring": [
            {
                "concept": e.concept,
                "category": e.category,
                "occurrences": e.occurrence_count,
                "example": e.user_input,
                "correct_form": e.correct_form,
                "needs_strategy_switch": e.strategy_switched,
            }
            for e in errors if e.occurrence_count >= 2
        ],
        "single_occurrence": [
            {
                "concept": e.concept,
                "category": e.category,
            }
            for e in errors if e.occurrence_count == 1
        ],
    }


# Resolve an Error

def mark_error_resolved(db: Session, profile_id: int, concept: str) -> bool:
    """
    Mark an error as resolved when the learner demonstrates mastery.
    Returns True if found and resolved, False if not found.
    """
    error = (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.concept == concept,
            ~Error.resolved,
        )
        .first()
    )
    if not error:
        return False

    error.resolved = True
    db.commit()
    return True


def mark_errors_resolved_bulk(db: Session, profile_id: int, concepts: list[str]) -> int:
    """Bulk resolve multiple concepts. Returns number of errors resolved."""
    updated = (
        db.query(Error)
        .filter(
            Error.learner_profile_id == profile_id,
            Error.concept.in_(concepts),
            Error.resolved == False,
        )
        .update({"resolved": True}, synchronize_session=False)
    )
    db.commit()
    return updated