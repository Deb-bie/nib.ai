"""
Tests for the curriculum planner.
"""

import pytest # type: ignore
from backend.agent.curriculum_planner import CurriculumPlanner
from backend.memory.error_tracker import log_error
from backend.memory.session_history import create_session, end_session
from backend.memory.learner_profile import get_current_curriculum_plan
from backend.config import MAX_ERRORS_BEFORE_STRATEGY_SWITCH, STAGNATION_SESSION_THRESHOLD


# Stagnation detection

class TestStagnationDetection:

    def _make_session_history(self, scores, errors_per_session=2):
        """Helper to build session history dicts from a list of scores."""
        return [
            {
                "session_id": i + 1,
                "performance_score": score,
                "errors_made": errors_per_session,
                "exercises_completed": 5,
                "exercises_correct": 3,
                "duration_minutes": 15,
                "session_type": "mixed",
                "agent_notes": "",
            }
            for i, score in enumerate(scores)
        ]

    def test_no_stagnation_with_few_sessions(self, db, test_profile):
        planner = CurriculumPlanner(db, test_profile.id)
        history = self._make_session_history([60, 65])  # only 2 sessions
        assert planner._detect_stagnation(history) is False

    def test_no_stagnation_when_improving(self, db, test_profile):
        planner = CurriculumPlanner(db, test_profile.id)
        history = self._make_session_history([50, 60, 75])  # improving scores
        assert planner._detect_stagnation(history) is False

    def test_stagnation_detected_flat_and_struggling(self, db, test_profile):
        planner = CurriculumPlanner(db, test_profile.id)
        # Flat scores + high error count = stagnation
        history = self._make_session_history([45, 46, 44], errors_per_session=5)
        assert planner._detect_stagnation(history) is True

    def test_no_stagnation_flat_but_few_errors(self, db, test_profile):
        planner = CurriculumPlanner(db, test_profile.id)
        # Flat scores but very few errors — learner is doing well, just plateaued
        history = self._make_session_history([88, 89, 87], errors_per_session=1)
        assert planner._detect_stagnation(history) is False

    def test_stagnation_threshold_exactly_met(self, db, test_profile):
        planner = CurriculumPlanner(db, test_profile.id)
        # Exactly STAGNATION_SESSION_THRESHOLD sessions of flat struggling
        history = self._make_session_history(
            [40] * STAGNATION_SESSION_THRESHOLD,
            errors_per_session=4,
        )
        assert planner._detect_stagnation(history) is True


# Plan generation

class TestCurriculumPlanGeneration:

    def test_plan_is_saved_to_db(self, db, seeded_profile, mock_groq):
        planner = CurriculumPlanner(db, seeded_profile.id)
        plan = planner.plan_next_session()

        assert plan is not None
        assert "session_focus" in plan
        assert "agent_reasoning" in plan

        # Check it was saved to DB
        saved = get_current_curriculum_plan(db, seeded_profile.id)
        assert saved is not None
        assert saved.is_current is True

    def test_session_focus_sums_to_100(self, db, seeded_profile, mock_groq):
        planner = CurriculumPlanner(db, seeded_profile.id)
        plan = planner.plan_next_session()
        total = sum(plan["session_focus"].values())
        assert total == 100

    def test_get_or_create_returns_existing_plan(self, db, seeded_profile, mock_groq):
        planner = CurriculumPlanner(db, seeded_profile.id)
        plan1 = planner.plan_next_session()

        # get_or_create should return the existing plan without regenerating
        plan2 = planner.get_or_create_plan()
        assert plan2["agent_reasoning"] == plan1["agent_reasoning"]

    def test_new_plan_deactivates_old_plan(self, db, seeded_profile, mock_groq):
        planner = CurriculumPlanner(db, seeded_profile.id)
        planner.plan_next_session()
        first_plan = get_current_curriculum_plan(db, seeded_profile.id)
        first_id = first_plan.id

        # Generate a second plan
        planner.plan_next_session()
        new_plan = get_current_curriculum_plan(db, seeded_profile.id)

        # New plan should be active, old one deactivated
        assert new_plan.id != first_id
        assert new_plan.is_current is True

        from backend.database.models import CurriculumPlan
        old = db.query(CurriculumPlan).filter(CurriculumPlan.id == first_id).first()
        assert old.is_current is False

    def test_plan_includes_due_reviews(self, db, seeded_profile, mock_groq):
        planner = CurriculumPlanner(db, seeded_profile.id)
        plan = planner.plan_next_session()
        # Seeded profile has vocab items, some should be due
        assert isinstance(plan["review_items"], list)


# Error strategy switching

class TestErrorStrategySwitch:

    def test_strategy_switch_after_threshold(self, db, test_profile):
        """Same error logged MAX_ERRORS times → strategy_switched becomes True."""
        error = None
        for _ in range(MAX_ERRORS_BEFORE_STRATEGY_SWITCH):
            error = log_error(
                db=db,
                profile_id=test_profile.id,
                session_id=None,
                category="verb_conjugation",
                concept="present_subjunctive",
                user_input="yo tengo",
                correct_form="yo tenga",
                explanation="",
            )
        assert error.strategy_switched is True
        assert error.occurrence_count == MAX_ERRORS_BEFORE_STRATEGY_SWITCH

    def test_no_strategy_switch_before_threshold(self, db, test_profile):
        for _ in range(MAX_ERRORS_BEFORE_STRATEGY_SWITCH - 1):
            error = log_error(
                db=db,
                profile_id=test_profile.id,
                session_id=None,
                category="verb_conjugation",
                concept="ser_vs_estar",
                user_input="yo estar cansado",
                correct_form="yo estoy cansado",
                explanation="",
            )
        assert error.strategy_switched is False

    def test_different_concepts_tracked_independently(self, db, test_profile):
        """Two different errors don't cross-contaminate occurrence counts."""
        for _ in range(MAX_ERRORS_BEFORE_STRATEGY_SWITCH):
            log_error(db, test_profile.id, None,
                      "verb_conjugation", "concept_A", "bad", "good", "")

        # concept_B only logged once — should NOT have strategy switch
        err_b = log_error(db, test_profile.id, None,
                          "noun_gender", "concept_B", "el mesa", "la mesa", "")
        assert err_b.strategy_switched is False
        assert err_b.occurrence_count == 1
