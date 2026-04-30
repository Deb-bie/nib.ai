"""
Session history — stores and retrieves tutoring session records.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session as DBSession # type: ignore

from database.models import Session, SessionMessage


# Session CRUD

def create_session(
    db: DBSession,
    profile_id: int,
    session_type: str = "mixed",
    planned_focus: dict = None,
    input_mode: str = "text",
) -> Session:
    session = Session(
        learner_profile_id=profile_id,
        session_type=session_type,
        planned_focus=planned_focus or {},
        input_mode=input_mode,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_id(db: DBSession, session_id: int) -> Optional[Session]:
    return db.query(Session).filter(Session.id == session_id).first()


def get_open_session_for_profile(db: DBSession, profile_id: int) -> Optional[Session]:
    """Return the most recent session that hasn't been ended yet (ended_at IS NULL)."""
    return (
        db.query(Session)
        .filter(
            Session.learner_profile_id == profile_id,
            Session.ended_at == None,  # noqa: E711
        )
        .order_by(Session.started_at.desc())
        .first()
    )


def end_session(
    db: DBSession,
    session_id: int,
    performance_score: float,
    errors_made: int,
    exercises_completed: int,
    exercises_correct: int,
    agent_summary: str,
    agent_notes: str,
    actual_focus: dict = None,
) -> Session:
    """Finalise a session when the user ends it or time runs out."""
    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    now = datetime.utcnow()
    session.ended_at = now
    session.duration_minutes = (now - session.started_at).total_seconds() / 60
    session.performance_score = performance_score
    session.errors_made = errors_made
    session.exercises_completed = exercises_completed
    session.exercises_correct = exercises_correct
    session.agent_summary = agent_summary
    session.agent_notes = agent_notes
    session.actual_focus = actual_focus or {}

    db.commit()
    db.refresh(session)
    return session


def get_recent_sessions(db: DBSession, profile_id: int, limit: int = 5) -> list[Session]:
    return (
        db.query(Session)
        .filter(Session.learner_profile_id == profile_id)
        .order_by(Session.started_at.desc())
        .limit(limit)
        .all()
    )


def get_all_sessions(db: DBSession, profile_id: int, limit: int = 100) -> list[Session]:
    return (
        db.query(Session)
        .filter(Session.learner_profile_id == profile_id)
        .order_by(Session.started_at.desc())
        .limit(limit)
        .all()
    )


def get_session_history_summary(db: DBSession, profile_id: int, limit: int = 5) -> list[dict]:
    """
    Returns recent sessions formatted for the curriculum planner.
    The agent uses this to detect stagnation across sessions.
    """
    sessions = get_recent_sessions(db, profile_id, limit)
    return [
        {
            "session_id": s.id,
            "date": s.started_at.isoformat(),
            "duration_minutes": round(s.duration_minutes or 0, 1),
            "performance_score": s.performance_score,
            "errors_made": s.errors_made,
            "exercises_correct": s.exercises_correct,
            "exercises_completed": s.exercises_completed,
            "session_type": s.session_type,
            "agent_notes": s.agent_notes,
        }
        for s in sessions
    ]


# Messages

def add_message(
    db: DBSession,
    session_id: int,
    role: str,
    content: str,
    audio_path: str = None,
    contains_error: bool = False,
) -> SessionMessage:
    msg = SessionMessage(
        session_id=session_id,
        role=role,
        content=content,
        audio_path=audio_path,
        contains_error=contains_error,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_session_messages(db: DBSession, session_id: int) -> list[SessionMessage]:
    return (
        db.query(SessionMessage)
        .filter(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.timestamp.asc())
        .all()
    )


def get_messages_for_llm(db: DBSession, session_id: int) -> list[dict]:
    """
    Returns messages in the format expected by the LLM (role + content dicts).
    Used to reconstruct conversation history in the LLM context window.
    """
    messages = get_session_messages(db, session_id)
    return [{"role": m.role, "content": m.content} for m in messages]