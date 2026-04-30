"""
Session Agent — runs the live tutoring session.

This is the agent the learner interacts with in real time.
It follows the curriculum plan, tracks errors as they happen,
adapts difficulty mid-session, and produces a full evaluation
when the session ends.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session # type: ignore

from llm.groq_client import chat, single_turn_json
from llm.prompt_builder import (
    build_session_system_prompt,
    build_session_evaluation_prompt,
)
from llm.response_parser import extract_session_evaluation
from memory.learner_profile import (
    get_full_learner_state,
    get_learner_profile_by_id,
    record_session_completed,
    update_skill_level,
)
from memory.session_history import (
    create_session,
    end_session,
    add_message,
    get_messages_for_llm,
)
from memory.error_tracker import (
    log_error,
    mark_errors_resolved_bulk,
    get_error_summary,
)
from memory.spaced_repetition import get_due_items_summary
from agent.curriculum_planner import CurriculumPlanner

logger = logging.getLogger(__name__)

import os as _os
MAX_USER_EXCHANGES: int = int(_os.getenv("MAX_SESSION_EXCHANGES", "8"))


class SessionAgent:
    """
    Manages a single tutoring session from start to finish.

    Usage:
        agent = SessionAgent(db, profile_id)
        opening = agent.start_session(input_mode="text")

        # During session:
        reply = agent.respond(user_message)

        # When session ends:
        summary = agent.end_session()
    """

    def __init__(self, db: Session, profile_id: int):
        self.db = db
        self.profile_id = profile_id
        self.profile = get_learner_profile_by_id(db, profile_id)
        if not self.profile:
            raise ValueError(f"Profile {profile_id} not found")

        self.session_id: int | None = None
        self.system_prompt: str = ""
        self.curriculum_plan: dict = {}
        self.is_active = False
        self._user_message_count: int = 0  # tracks exchanges for session limit

    # Session Start

    def start_session(self, input_mode: str = "text") -> str:
        """
        Initialise the session:
        1. Load the curriculum plan
        2. Build the system prompt
        3. Create a session record in the DB
        4. Generate the opening message

        Returns the tutor's opening message.
        """
        # Load current plan (or create one if none exists)
        planner = CurriculumPlanner(self.db, self.profile_id)
        self.curriculum_plan = planner.get_or_create_plan()

        # Load full learner state
        learner_state = get_full_learner_state(self.db, self.profile_id)
        due_reviews = get_due_items_summary(self.db, self.profile_id)

        user = self.profile.user
        native = user.native_language if user else "english"

        # Build system prompt
        self.system_prompt = build_session_system_prompt(
            learner_state=learner_state,
            curriculum_plan=self.curriculum_plan,
            due_review_words=due_reviews.get("items", []),
            target_language=self.profile.target_language,
            native_language=native,
        )

        # Create session record in DB
        session = create_session(
            db=self.db,
            profile_id=self.profile_id,
            session_type=self._determine_session_type(),
            planned_focus=self.curriculum_plan.get("session_focus", {}),
            input_mode=input_mode,
        )
        self.session_id = session.id
        self.is_active = True

        # Build context note about previous session (recap + continuation)
        begin_context = self._build_begin_context()

        # Generate opening message
        opening = chat(
            messages=[{"role": "user", "content": begin_context}],
            system_prompt=self.system_prompt,
            temperature=0.8,
        )

        # Save opening message to DB
        add_message(self.db, self.session_id, "assistant", opening)

        logger.info(
            f"Session {self.session_id} started for profile {self.profile_id}. "
            f"Mode: {input_mode}. Plan focus: {self.curriculum_plan.get('session_focus')}"
        )
        return opening

    # Session Context Builder

    def _build_begin_context(self) -> str:
        """
        Build the [BEGIN SESSION] trigger message.
        Includes a brief recap of the previous session so the agent can
        open with continuity, and flags any incomplete session.
        """
        from memory.session_history import get_session_history_summary, get_open_session_for_profile

        parts = ["[BEGIN SESSION]"]

        # Check for a lingering open session (server restart mid-session)
        open_sess = get_open_session_for_profile(self.db, self.profile_id)
        if open_sess and open_sess.id != self.session_id:
            parts.append(
                "\n\n[CONTEXT: The learner's previous session was interrupted before completion. "
                "Begin by briefly acknowledging where they left off and continue from there.]"
            )

        # Include last completed session recap
        try:
            history = get_session_history_summary(self.db, self.profile_id, limit=2)
            # Find the most recent *completed* session (not the one we just created)
            completed = [s for s in history if s.get("performance_score") is not None
                         and s.get("session_id") != self.session_id]
            if completed:
                last = completed[0]
                score = last.get("performance_score", 0)
                errors = last.get("errors_made", 0)
                notes  = last.get("agent_notes", "")
                recap  = (
                    f"\n\n[PREVIOUS SESSION RECAP: Score {score:.0f}/100, "
                    f"{errors} error(s). "
                )
                if notes:
                    recap += f"Notes from last session: {notes[:200]}. "
                recap += (
                    "Briefly recap what was covered, praise any progress, "
                    "and smoothly introduce today's focus.]"
                )
                parts.append(recap)
        except Exception:
            pass  # recap is best-effort

        return "".join(parts)

    # Turn-by-Turn Conversation

    def respond(self, user_message: str) -> str:
        """
        Process a learner message and return the tutor's reply.
        Automatically saves both messages to the session history.
        """
        if not self.is_active or not self.session_id:
            raise RuntimeError("Session is not active. Call start_session() first.")

        # Save user message
        add_message(self.db, self.session_id, "user", user_message)
        self._user_message_count += 1

        # Get full conversation history for context window
        history = get_messages_for_llm(self.db, self.session_id)

        # If the session limit is about to be hit, ask the agent to wrap up
        remaining = MAX_USER_EXCHANGES - self._user_message_count
        extra_instruction = ""
        if remaining <= 1:
            extra_instruction = (
                "\n\n[SYSTEM NOTE: This is the learner's last message this session. "
                "Give a warm closing response, summarise what was covered, and say goodbye.]"
            )
        elif remaining <= 2:
            extra_instruction = (
                "\n\n[SYSTEM NOTE: Only one more exchange after this. "
                "Begin wrapping up the session naturally.]"
            )

        reply = chat(
            messages=history,
            system_prompt=self.system_prompt + extra_instruction,
            temperature=0.7,
        )

        # Save tutor reply
        add_message(self.db, self.session_id, "assistant", reply)

        return reply

    def is_limit_reached(self) -> bool:
        """True once the user has sent MAX_USER_EXCHANGES messages."""
        return self._user_message_count >= MAX_USER_EXCHANGES

    # Session End

    def end_session(self) -> dict:
        """
        End the session:
        1. Run the evaluation LLM call on the full conversation
        2. Log all errors to the error tracker
        3. Update skill levels based on performance
        4. Mark mastered concepts as resolved
        5. Update learner profile stats
        6. Trigger the curriculum planner to generate the next plan
        7. Return the session summary

        Returns a summary dict for the frontend to display.
        """
        if not self.session_id:
            raise RuntimeError("No active session to end.")

        self.is_active = False

        # Get full conversation
        history = get_messages_for_llm(self.db, self.session_id)

        if len(history) < 2:
            # Nothing happened — end cleanly
            return {"summary": "Session ended without any exchanges.", "performance_score": 0}

        user = self.profile.user
        native = user.native_language if user else "english"

        # Run evaluation
        eval_prompt = build_session_evaluation_prompt(
            conversation_history=history,
            planned_focus=self.curriculum_plan.get("session_focus", {}),
            target_language=self.profile.target_language,
        )

        from llm.response_parser import extract_session_evaluation
        raw = single_turn_json(eval_prompt, temperature=0.2, max_tokens=2048)
        evaluation = extract_session_evaluation(raw)

        # Log errors to error tracker
        errors_logged = self._log_session_errors(evaluation.get("errors", []))

        # Update skill levels
        self._update_skill_levels(evaluation.get("skill_updates", {}))

        # Mark mastered concepts as resolved in error tracker
        mastered = evaluation.get("mastered_concepts", [])
        if mastered:
            mark_errors_resolved_bulk(self.db, self.profile_id, mastered)

        # Finalise session record
        end_session(
            db=self.db,
            session_id=self.session_id,
            performance_score=evaluation["performance_score"],
            errors_made=len(evaluation.get("errors", [])),
            exercises_completed=evaluation["exercises_completed"],
            exercises_correct=evaluation["exercises_correct"],
            agent_summary=evaluation["summary"],
            agent_notes=evaluation["notes_for_next_session"],
            actual_focus=self.curriculum_plan.get("session_focus", {}),
        )

        # Update profile stats
        record_session_completed(self.db, self.profile_id, duration_minutes=15.0)

        # Trigger curriculum planner to prepare next session plan
        self._plan_next_session_async()

        logger.info(
            f"Session {self.session_id} ended. "
            f"Score: {evaluation['performance_score']}. "
            f"Errors: {len(evaluation.get('errors', []))}."
        )

        return {
            "session_id": self.session_id,
            "performance_score": evaluation["performance_score"],
            "summary": evaluation["summary"],
            "errors_made": len(evaluation.get("errors", [])),
            "exercises_completed": evaluation["exercises_completed"],
            "exercises_correct": evaluation["exercises_correct"],
            "mastered_concepts": mastered,
        }

    # Internal Helpers

    def _log_session_errors(self, errors: list[dict]) -> int:
        """Log all errors extracted from the session evaluation."""
        count = 0
        for e in errors:
            try:
                log_error(
                    db=self.db,
                    profile_id=self.profile_id,
                    session_id=self.session_id,
                    category=e.get("category", "unknown"),
                    concept=e.get("concept", "unknown"),
                    user_input=e.get("user_input", ""),
                    correct_form=e.get("correct_form", ""),
                    explanation=e.get("explanation", ""),
                )
                count += 1
            except Exception as ex:
                logger.warning(f"Failed to log error: {ex}")
        return count

    def _update_skill_levels(self, skill_updates: dict) -> None:
        """Apply skill score deltas from the session evaluation."""
        for skill, delta in skill_updates.items():
            try:
                update_skill_level(self.db, self.profile_id, skill, float(delta))
            except Exception as ex:
                logger.warning(f"Failed to update skill {skill}: {ex}")

    def _determine_session_type(self) -> str:
        """Infer session type from the curriculum plan's focus distribution."""
        focus = self.curriculum_plan.get("session_focus", {})
        if not focus:
            return "mixed"
        dominant = max(focus, key=focus.get)
        if focus[dominant] >= 70:
            return dominant
        return "mixed"

    def _plan_next_session_async(self) -> None:
        """
        Trigger the curriculum planner to generate the next session plan.
        Runs synchronously for now — can be moved to a background task later.
        """
        try:
            planner = CurriculumPlanner(self.db, self.profile_id)
            planner.plan_next_session()
        except Exception as e:
            logger.error(f"Failed to plan next session: {e}")