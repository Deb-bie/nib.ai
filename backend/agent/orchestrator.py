"""
Orchestrator — the single entry point for all agent interactions.

The FastAPI routes only talk to this class. It coordinates:
    - Which agent to invoke for a given action
    - Session state management
    - Routing between assessment and tutoring modes
    - Error handling and graceful degradation
"""

import logging
from sqlalchemy.orm import Session # type: ignore

from agent.assessment_agent import AssessmentAgent
from agent.session_agent import SessionAgent
from agent.curriculum_planner import CurriculumPlanner
from memory.learner_profile import (
    create_user,
    create_learner_profile,
    get_full_learner_state,
)
from memory.session_history import get_session_history_summary, get_open_session_for_profile, end_session as db_end_session
from memory.error_tracker import get_error_summary
from memory.spaced_repetition import get_vocabulary_stats
from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


_active_sessions: dict[int, SessionAgent] = {}
_active_assessments: dict[int, AssessmentAgent] = {}


class Orchestrator:
    """
    Coordinates all agent activity for a single learner profile.

    Usage:
        orch = Orchestrator(db, profile_id)

        # Start a session:
        opening = orch.start_session()

        # Send a message:
        reply = orch.send_message("Hola, ¿cómo estás?")

        # End session:
        summary = orch.end_session()
    """

    def __init__(self, db: Session, profile_id: int):
        self.db = db
        self.profile_id = profile_id

    # Onboarding

    @staticmethod
    def create_new_user(
        db: Session,
        username: str,
        email: str,
        native_language: str,
        target_language: str,
        learning_goal: str = "conversational",
        password_hash: str = "",      
    ) -> dict:
        """
        Full onboarding flow for a new user.
        Creates user, creates learner profile, returns state.
        """
        if target_language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Language '{target_language}' not supported. "
                f"Supported: {list(SUPPORTED_LANGUAGES.keys())}"
            )

        # Create user
        user = create_user(db, username, email, native_language, password_hash)

        # Create learner profile — starts at A1 (beginner)
        profile = create_learner_profile(
            db=db,
            user_id=user.id,
            target_language=target_language,
            learning_goal=learning_goal,
            initial_level="A1",
        )

        logger.info(f"New user created: {username}, learning {target_language}")

        return {
            "user_id": user.id,
            "profile_id": profile.id,
            "username": username,
            "target_language": target_language,
            "needs_assessment": True,
        }

    # Assessment Flow

    def start_assessment(self) -> str:
        """
        Start a placement assessment for this profile.
        Returns the first message from the assessment agent.
        """
        agent = AssessmentAgent(self.db, self.profile_id)
        opening = agent.get_opening_message()
        _active_assessments[self.profile_id] = agent
        logger.info(f"Assessment started for profile {self.profile_id}")
        return opening

    def send_assessment_message(self, user_message: str) -> dict:
        """
        Send a message during an active assessment.

        Returns:
            {
                "reply": str,
                "is_complete": bool,
                "result": dict | None  # assessment result if complete
            }
        """
        agent = _active_assessments.get(self.profile_id)
        if not agent:
            raise RuntimeError("No active assessment. Call start_assessment() first.")

        reply, is_complete = agent.respond(user_message)

        result = None
        if is_complete:
            result = agent.evaluate_and_save()
            del _active_assessments[self.profile_id]

            # Seed vocabulary and grammar for the assessed level
            from database.seed_loader import seed_learner_profile
            seed_learner_profile(
                db=self.db,
                profile_id=self.profile_id,
                target_language=self.profile.target_language,
                current_level=result.get("overall_level", "A1"),
            )

            # After assessment, generate the first curriculum plan
            planner = CurriculumPlanner(self.db, self.profile_id)
            planner.plan_next_session()
            logger.info(f"Assessment complete, first plan generated for profile {self.profile_id}")

        return {
            "reply": reply,
            "is_complete": is_complete,
            "result": result,
        }

    # Session Flow

    def start_session(self, input_mode: str = "text") -> dict:
        """
        Start a tutoring session.
        If another session is already in-memory it is gracefully ended first,
        so callers never get a 409 conflict on legitimate restarts.

        Returns:
            {
                "session_id": int,
                "opening_message": str,
                "plan_summary": dict,
            }
        """
        # Auto-end any in-memory session rather than blocking with 409
        if self.profile_id in _active_sessions:
            logger.info(
                f"Auto-ending existing in-memory session for profile {self.profile_id}"
            )
            stale = _active_sessions.pop(self.profile_id)
            try:
                stale.end_session()
            except Exception:
                pass

        agent = SessionAgent(self.db, self.profile_id)
        opening = agent.start_session(input_mode=input_mode)
        _active_sessions[self.profile_id] = agent

        return {
            "session_id": agent.session_id,
            "opening_message": opening,
            "plan_summary": {
                "focus": agent.curriculum_plan.get("session_focus"),
                "reasoning": agent.curriculum_plan.get("agent_reasoning", "")[:200],
                "priority_concepts": agent.curriculum_plan.get("priority_concepts", [])[:3],
                "review_count": len(agent.curriculum_plan.get("review_items", [])),
            },
        }

    def send_message(self, user_message: str) -> str:
        """
        Send a message in the active session.
        Returns the tutor's reply.
        """
        agent = _active_sessions.get(self.profile_id)
        if not agent:
            raise RuntimeError("No active session. Call start_session() first.")
        return agent.respond(user_message)

    def end_session(self) -> dict:
        """
        End the active session and return the summary.
        If the in-memory agent is gone (e.g. server restart), fall back to
        closing the most recent open DB session with a minimal summary.
        """
        agent = _active_sessions.pop(self.profile_id, None)
        if agent:
            return agent.end_session()

        # Fallback: server was restarted — close open DB session gracefully
        open_sess = get_open_session_for_profile(self.db, self.profile_id)
        if open_sess:
            db_end_session(
                db=self.db,
                session_id=open_sess.id,
                performance_score=0.0,
                errors_made=0,
                exercises_completed=0,
                exercises_correct=0,
                agent_summary="Session ended (server was restarted during this session).",
                agent_notes="",
                actual_focus={},
            )
            return {
                "session_id": open_sess.id,
                "performance_score": 0,
                "summary": "Session ended. The server restarted mid-session so no evaluation was run.",
                "errors_made": 0,
                "exercises_completed": 0,
                "exercises_correct": 0,
                "mastered_concepts": [],
            }

        
        raise RuntimeError("No active session found for this profile.")

    def is_session_limit_reached(self) -> bool:
        """True if the active session has hit the per-session exchange cap."""
        agent = _active_sessions.get(self.profile_id)
        return agent.is_limit_reached() if agent else False

    def has_active_session(self) -> bool:
        return self.profile_id in _active_sessions

    def has_active_assessment(self) -> bool:
        return self.profile_id in _active_assessments

    # Learner Dashboard Data

    def get_dashboard_data(self) -> dict:
        """
        Returns everything the frontend needs to render the dashboard:
        learner state, recent sessions, errors, vocab stats, and current plan.
        """
        learner_state = get_full_learner_state(self.db, self.profile_id)
        session_history = get_session_history_summary(self.db, self.profile_id, limit=10)
        error_summary = get_error_summary(self.db, self.profile_id)
        vocab_stats = get_vocabulary_stats(self.db, self.profile_id)

        return {
            "learner": learner_state,
            "recent_sessions": session_history,
            "errors": error_summary,
            "vocabulary": vocab_stats,
        }