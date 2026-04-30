"""
Session API routes.

POST /session/start               — start a tutoring session
POST /session/message             — send a message in the active session
POST /session/end                 — end the session and get the summary
GET  /session/status/{id}         — check if a session is active
GET  /session/history/{profile_id} — all past sessions for a profile
GET  /session/{session_id}/messages — full message log for one session
"""

from fastapi import APIRouter, Depends, HTTPException # type: ignore
from pydantic import BaseModel # type: ignore
from sqlalchemy.orm import Session # type: ignore

from database.db import get_db
from agent.orchestrator import Orchestrator
from memory.session_history import get_all_sessions, get_session_messages

router = APIRouter(prefix="/session", tags=["Session"])


# Request / Response Models

class StartSessionRequest(BaseModel):
    profile_id: int
    input_mode: str = "text"

class MessageRequest(BaseModel):
    profile_id: int
    message: str

class EndSessionRequest(BaseModel):
    profile_id: int


# Routes

@router.post("/start")
def start_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    try:
        orch = Orchestrator(db, req.profile_id)
        result = orch.start_session(input_mode=req.input_mode)
        return {"success": True, **result}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/message")
def send_message(req: MessageRequest, db: Session = Depends(get_db)):
    try:
        orch = Orchestrator(db, req.profile_id)
        reply = orch.send_message(req.message)
        session_complete = orch.is_session_limit_reached()
        return {"success": True, "reply": reply, "session_complete": session_complete}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/end")
def end_session(req: EndSessionRequest, db: Session = Depends(get_db)):
    orch = Orchestrator(db, req.profile_id)
    summary = orch.end_session()
    return {"success": True, **summary}


@router.get("/status/{profile_id}")
def session_status(profile_id: int, db: Session = Depends(get_db)):
    orch = Orchestrator(db, profile_id)
    return {
        "has_active_session": orch.has_active_session(),
        "has_active_assessment": orch.has_active_assessment(),
    }


@router.get("/history/{profile_id}")
def session_history(profile_id: int, db: Session = Depends(get_db)):
    """Return all past sessions for a learner profile (newest first)."""
    sessions = get_all_sessions(db, profile_id, limit=100)
    return {
        "success": True,
        "total": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration_minutes": round(s.duration_minutes or 0, 1),
                "session_type": s.session_type,
                "input_mode": s.input_mode,
                "performance_score": s.performance_score,
                "exercises_completed": s.exercises_completed,
                "exercises_correct": s.exercises_correct,
                "errors_made": s.errors_made,
                "agent_summary": s.agent_summary,
                "agent_notes": s.agent_notes,
                "completed": s.ended_at is not None,
            }
            for s in sessions
        ],
    }


@router.get("/{session_id}/messages")
def session_messages(session_id: int, db: Session = Depends(get_db)):
    """Return full message transcript for a specific session."""
    msgs = get_session_messages(db, session_id)
    return {
        "success": True,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "contains_error": m.contains_error,
            }
            for m in msgs
        ],
    }
