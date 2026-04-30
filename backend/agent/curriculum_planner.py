"""
Curriculum Planner — the core agentic decision-maker.

The planner reads the learner's complete state and autonomously decides what the next session should
cover, which strategies to use, and what problems need attention.

It runs AFTER every session ends and BEFORE every session begins.
The resulting plan is stored in the DB so the agent's reasoning is
always visible and explainable.
"""

import logging
from sqlalchemy.orm import Session # type: ignore

from llm.groq_client import single_turn_json
from llm.prompt_builder import build_curriculum_planner_prompt
from llm.response_parser import extract_curriculum_plan
from memory.learner_profile import (
    get_full_learner_state,
    get_learner_profile_by_id,
    save_curriculum_plan,
)
from memory.error_tracker import get_error_summary
from memory.session_history import get_session_history_summary
from memory.spaced_repetition import get_due_items_summary
from config import STAGNATION_SESSION_THRESHOLD

logger = logging.getLogger(__name__)


class CurriculumPlanner:
    """
    Reads the learner's full state and autonomously plans the next session.

    This is the agent that:
    - Decides what to teach (vocabulary vs grammar vs conversation ratio)
    - Identifies which concepts need the most attention
    - Detects when a teaching strategy isn't working and switches it
    - Detects stagnation and changes the approach
    - Ensures spaced repetition reviews always happen on schedule

    Usage:
        planner = CurriculumPlanner(db, profile_id)
        plan = planner.plan_next_session()
    """

    def __init__(self, db: Session, profile_id: int):
        self.db = db
        self.profile_id = profile_id
        self.profile = get_learner_profile_by_id(db, profile_id)
        if not self.profile:
            raise ValueError(f"Profile {profile_id} not found")

    # Main Planning Method

    def plan_next_session(self) -> dict:
        """
        Core method. Gathers all learner data, asks the LLM to reason
        about it, and saves the resulting plan.

        Returns the curriculum plan dict.
        """
        logger.info(f"Planning next session for profile {self.profile_id}")

        # Gather all context the planner needs
        learner_state = get_full_learner_state(self.db, self.profile_id)
        error_summary = get_error_summary(self.db, self.profile_id)
        session_history = get_session_history_summary(self.db, self.profile_id, limit=5)
        due_reviews = get_due_items_summary(self.db, self.profile_id)

        # Add stagnation detection to learner state
        stagnation = self._detect_stagnation(session_history)
        if stagnation:
            learner_state["stagnation_detected"] = True
            logger.warning(f"Stagnation detected for profile {self.profile_id}")

        # Build prompt and call LLM
        prompt = build_curriculum_planner_prompt(
            learner_state=learner_state,
            error_summary=error_summary,
            session_history=session_history,
            due_reviews=due_reviews,
        )

        raw = single_turn_json(prompt, temperature=0.3)
        plan = extract_curriculum_plan(raw)

        # Merge in due review words
        plan["review_items"] = [
            item["word"] for item in due_reviews.get("items", [])
        ]

        # Save plan to DB (this deactivates the previous plan)
        saved = save_curriculum_plan(
            db=self.db,
            profile_id=self.profile_id,
            session_focus=plan["session_focus"],
            priority_concepts=plan["priority_concepts"],
            concepts_to_skip=plan["concepts_to_skip"],
            review_items=plan["review_items"],
            agent_reasoning=plan["agent_reasoning"],
            detected_issues=plan["detected_issues"],
            strategy_overrides=plan["strategy_overrides"],
        )

        logger.info(
            f"Session plan saved for profile {self.profile_id}. "
            f"Focus: {plan['session_focus']}. "
            f"Priority concepts: {len(plan['priority_concepts'])}. "
            f"Reasoning: {plan['agent_reasoning'][:80]}..."
        )

        return plan

    # Stagnation Detection

    def _detect_stagnation(self, session_history: list[dict]) -> bool:
        """
        Detects if the learner is stagnating — no meaningful improvement
        across the last N sessions.

        Stagnation is defined as:
        - At least STAGNATION_SESSION_THRESHOLD sessions completed
        - Performance score not improving (variance < 5 points)
        - Error count not decreasing
        """
        if len(session_history) < STAGNATION_SESSION_THRESHOLD:
            return False

        recent = session_history[:STAGNATION_SESSION_THRESHOLD]
        scores = [s["performance_score"] for s in recent if s["performance_score"] is not None]

        if len(scores) < STAGNATION_SESSION_THRESHOLD:
            return False

        score_range = max(scores) - min(scores)
        avg_errors = sum(s["errors_made"] for s in recent) / len(recent)

        # Stagnating if scores are flat AND error count is still high
        is_flat = score_range < 5.0
        is_struggling = avg_errors > 3

        return is_flat and is_struggling

    # Lightweight Pre-session Plan

    def get_or_create_plan(self) -> dict:
        """
        Returns the current plan if one exists, or creates a new one.
        Use this at session start — avoids regenerating the plan if
        it was already made after the last session.
        """
        from memory.learner_profile import get_current_curriculum_plan

        existing = get_current_curriculum_plan(self.db, self.profile_id)
        if existing:
            return {
                "session_focus": existing.session_focus or {},
                "priority_concepts": existing.priority_concepts or [],
                "concepts_to_skip": existing.concepts_to_skip or [],
                "review_items": existing.review_items or [],
                "agent_reasoning": existing.agent_reasoning or "",
                "detected_issues": existing.detected_issues or [],
                "strategy_overrides": existing.strategy_overrides or {},
            }

        # No plan exists — create one now
        return self.plan_next_session()