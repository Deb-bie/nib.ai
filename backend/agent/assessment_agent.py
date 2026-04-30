"""
Assessment Agent.

Runs the initial placement test when a learner starts a new language,
and periodic re-assessments to recalibrate level if progress stalls.

Flow:
    1. Conducts a conversational diagnostic (5–8 exchanges)
    2. Evaluates the conversation and determines CEFR levels per skill
    3. Writes results back to the learner profile
    4. Returns the assessment result for the curriculum planner to use
"""

import logging
from sqlalchemy.orm import Session # type: ignore

from llm.groq_client import chat, single_turn_json
from llm.prompt_builder import (
    build_assessment_system_prompt,
    build_assessment_evaluation_prompt,
)
from llm.response_parser import extract_assessment_result
from memory.learner_profile import (
    get_learner_profile_by_id,
    update_overall_level,
)
from database.models import SkillLevel
from config import CEFR_LEVELS

logger = logging.getLogger(__name__)


class AssessmentAgent:
    """
    Runs placement and re-assessment tests.

    Usage:
        agent = AssessmentAgent(db, profile_id)

        # During assessment conversation:
        reply = agent.respond(user_message)

        # When assessment is complete:
        result = agent.evaluate_and_save()
    """

    def __init__(self, db: Session, profile_id: int):
        self.db = db
        self.profile = get_learner_profile_by_id(db, profile_id)
        if not self.profile:
            raise ValueError(f"Profile {profile_id} not found")

        self.profile_id = profile_id
        self.conversation_history: list[dict] = []
        self.exchange_count = 0
        self.max_exchanges = 8
        self.is_complete = False

    # Conversation

    def get_opening_message(self) -> str:
        """
        Generate the first message from the tutor to kick off the assessment.
        Called once before the learner has said anything.
        """
        user = self.profile.user
        native = user.native_language if user else "english"
        lang = self.profile.target_language

        system = build_assessment_system_prompt(
            target_language=lang,
            native_language=native,
            claimed_level="unsure",
        )

        opening = chat(
            messages=[{"role": "user", "content": "[START ASSESSMENT]"}],
            system_prompt=system,
            temperature=0.7,
        )

        self.conversation_history.append({"role": "assistant", "content": opening})
        self.exchange_count += 1
        return opening

    def respond(self, user_message: str) -> tuple[str, bool]:
        """
        Process a learner message during the assessment conversation.

        Returns:
            (tutor_reply, is_complete) — is_complete=True when enough data collected
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        user = self.profile.user
        native = user.native_language if user else "english"
        lang = self.profile.target_language

        system = build_assessment_system_prompt(
            target_language=lang,
            native_language=native,
            claimed_level="unsure",
        )

        # Signal to end assessment after enough exchanges
        messages_to_send = list(self.conversation_history)
        if self.exchange_count >= self.max_exchanges - 1:
            messages_to_send.append({
                "role": "user",
                "content": "[ASSESSMENT COMPLETE — wrap up the conversation naturally]",
            })

        reply = chat(messages=messages_to_send, system_prompt=system, temperature=0.7)

        self.conversation_history.append({"role": "assistant", "content": reply})
        self.exchange_count += 1

        # Mark complete after enough exchanges
        if self.exchange_count >= self.max_exchanges:
            self.is_complete = True

        return reply, self.is_complete

    # Evaluation

    def evaluate_and_save(self) -> dict:
        """
        Run the evaluation LLM call on the completed conversation,
        parse the result, and write it to the learner profile.

        Returns the assessment result dict.
        """
        if len(self.conversation_history) < 2:
            raise ValueError("Not enough conversation to evaluate")

        user = self.profile.user
        native = user.native_language if user else "english"

        eval_prompt = build_assessment_evaluation_prompt(
            conversation_history=self.conversation_history,
            target_language=self.profile.target_language,
            native_language=native,
        )

        raw = single_turn_json(eval_prompt, temperature=0.2)
        result = extract_assessment_result(raw)

        # Write results to DB
        self._save_assessment_result(result)

        logger.info(
            f"Assessment complete for profile {self.profile_id}: "
            f"overall={result['overall_level']}"
        )
        return result

    def _save_assessment_result(self, result: dict) -> None:
        """Write assessment results into the learner profile and skill levels."""
        # Update overall level
        update_overall_level(self.db, self.profile_id, result["overall_level"])

        # Update individual skill levels
        skill_levels = result.get("skill_levels", {})
        for skill, level in skill_levels.items():
            existing = (
                self.db.query(SkillLevel)
                .filter(
                    SkillLevel.learner_profile_id == self.profile_id,
                    SkillLevel.skill == skill,
                )
                .first()
            )
            if existing and level in CEFR_LEVELS:
                existing.level = level
                existing.score = 0.0

        self.db.commit()
        logger.debug(f"Saved assessment results for profile {self.profile_id}")


# Re-assessment Check

def should_reassess(sessions_completed: int, stagnation_detected: bool) -> bool:
    """
    Determine whether a re-assessment should be triggered.
    Called by the curriculum planner.

    Triggers re-assessment if:
    - Every 20 sessions (regular calibration)
    - Stagnation has been detected (no improvement in 3+ sessions)
    """
    if stagnation_detected:
        return True
    if sessions_completed > 0 and sessions_completed % 20 == 0:
        return True
    return False