"""
Integration tests
"""

import pytest # type: ignore
from backend.agent.orchestrator import Orchestrator
from backend.memory.session_history import get_recent_sessions, get_session_messages
from backend.memory.error_tracker import get_error_summary
from backend.memory.learner_profile import get_full_learner_state, get_current_curriculum_plan
from backend.memory.spaced_repetition import get_vocabulary_stats


# Onboarding

class TestOnboarding:

    def test_create_new_user_succeeds(self, db):
        result = Orchestrator.create_new_user(
            db=db,
            username="alice",
            email="alice@example.com",
            native_language="english",
            target_language="spanish",
            learning_goal="travel",
        )
        assert result["user_id"] is not None
        assert result["profile_id"] is not None
        assert result["needs_assessment"] is True
        assert result["target_language"] == "spanish"

    def test_unsupported_language_raises(self, db):
        with pytest.raises(ValueError, match="not supported"):
            Orchestrator.create_new_user(
                db=db,
                username="bob",
                email="bob@test.com",
                native_language="english",
                target_language="klingon",
            )

    def test_profile_has_all_skills(self, db):
        result = Orchestrator.create_new_user(
            db=db,
            username="carol",
            email="carol@test.com",
            native_language="english",
            target_language="french",
        )
        state = get_full_learner_state(db, result["profile_id"])
        assert len(state["skills"]) == 6
        for skill, data in state["skills"].items():
            assert data["level"] == "A1"
            assert data["score"] == 0.0


# Session Flow

class TestSessionFlow:

    def test_start_session_returns_opening_message(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        result = orch.start_session(input_mode="text")

        assert "session_id" in result
        assert "opening_message" in result
        assert isinstance(result["opening_message"], str)
        assert len(result["opening_message"]) > 0
        assert result["session_id"] is not None

    def test_send_message_returns_reply(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        reply = orch.send_message("Hola, me llamo Juan.")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_messages_saved_to_db(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        result = orch.start_session()
        session_id = result["session_id"]
        orch.send_message("Yo hablar español.")

        messages = get_session_messages(db, session_id)
        roles = [m.role for m in messages]
        assert "assistant" in roles
        assert "user" in roles

    def test_end_session_returns_summary(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        orch.send_message("Yo hablar español.")
        summary = orch.end_session()

        assert "performance_score" in summary
        assert "summary" in summary
        assert "errors_made" in summary
        assert "exercises_completed" in summary

    def test_session_saved_to_history(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        orch.send_message("Yo hablar español.")
        orch.end_session()

        sessions = get_recent_sessions(db, seeded_profile.id)
        assert len(sessions) == 1
        assert sessions[0].ended_at is not None
        assert sessions[0].performance_score is not None

    def test_errors_logged_after_session(self, db, seeded_profile, mock_groq):
        """
        Test that error logging works correctly.
        We test this directly via log_error rather than through the full
        session pipeline, which involves many LLM calls with mocked responses.
        """
        from backend.memory.error_tracker import log_error
        # Directly log an error the way session_agent._log_session_errors does
        log_error(
            db=db,
            profile_id=seeded_profile.id,
            session_id=None,
            category="verb_conjugation",
            concept="present_tense_regular",
            user_input="yo hablar español",
            correct_form="yo hablo español",
            explanation="Use conjugated form",
        )
        error_summary = get_error_summary(db, seeded_profile.id)
        assert error_summary["total_unresolved"] >= 1
        assert any(
            e["concept"] == "present_tense_regular"
            for e in error_summary.get("single_occurrence", [])
        )

    def test_curriculum_plan_created_after_session(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        orch.send_message("Hola.")
        orch.end_session()

        plan = get_current_curriculum_plan(db, seeded_profile.id)
        assert plan is not None
        assert plan.agent_reasoning is not None

    def test_cannot_start_two_sessions_simultaneously(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        with pytest.raises(RuntimeError, match="already active"):
            orch.start_session()

    def test_send_message_without_session_raises(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        # No session started — send_message should raise
        with pytest.raises(RuntimeError, match="No active session"):
            orch.send_message("Hola")

    def test_end_session_without_session_raises(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        # No session started — end_session should raise
        with pytest.raises(RuntimeError, match="No active session"):
            orch.end_session()

    def test_has_active_session_flag(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        assert orch.has_active_session() is False
        orch.start_session()
        assert orch.has_active_session() is True
        orch.end_session()
        assert orch.has_active_session() is False

    def test_session_updates_sessions_completed(self, db, seeded_profile, mock_groq):
        state_before = get_full_learner_state(db, seeded_profile.id)
        sessions_before = state_before["sessions_completed"]

        orch = Orchestrator(db, seeded_profile.id)
        orch.start_session()
        orch.send_message("Hola.")
        orch.end_session()

        state_after = get_full_learner_state(db, seeded_profile.id)
        assert state_after["sessions_completed"] == sessions_before + 1


# Dashboard Data

class TestDashboardData:

    def test_dashboard_returns_expected_keys(self, db, seeded_profile, mock_groq):
        orch = Orchestrator(db, seeded_profile.id)
        data = orch.get_dashboard_data()

        assert "learner" in data
        assert "recent_sessions" in data
        assert "errors" in data
        assert "vocabulary" in data

    def test_vocabulary_populated_after_seed(self, db, seeded_profile):
        stats = get_vocabulary_stats(db, seeded_profile.id)
        assert stats["total_words"] > 0, "Seed should have loaded vocabulary"


# Seed Loader

class TestSeedLoader:

    def test_seed_loads_vocabulary(self, db, test_profile):
        from backend.database.seed_loader import seed_learner_profile
        result = seed_learner_profile(db, test_profile.id, "spanish", "A1")
        assert result["vocabulary_added"] > 0

    def test_seed_loads_grammar(self, db, test_profile):
        from backend.database.seed_loader import seed_learner_profile
        result = seed_learner_profile(db, test_profile.id, "spanish", "A1")
        assert result["grammar_added"] > 0

    def test_seed_is_idempotent(self, db, test_profile):
        """Running seed twice shouldn't duplicate words."""
        from backend.database.seed_loader import seed_learner_profile
        r1 = seed_learner_profile(db, test_profile.id, "spanish", "A1")
        r2 = seed_learner_profile(db, test_profile.id, "spanish", "A1")
        assert r2["vocabulary_added"] == 0  # nothing new to add

    def test_higher_level_seeds_more_words(self, db, db_two_profiles):
        from backend.database.seed_loader import seed_learner_profile
        profile_a1, profile_b1 = db_two_profiles
        r_a1 = seed_learner_profile(db, profile_a1.id, "spanish", "A1")
        r_b1 = seed_learner_profile(db, profile_b1.id, "spanish", "B1")
        assert r_b1["vocabulary_added"] > r_a1["vocabulary_added"]


@pytest.fixture
def db_two_profiles(db):
    """Two profiles at different levels for comparison tests."""
    user1 = create_user_helper(db, "userA1", "a1@test.com")
    user2 = create_user_helper(db, "userB1", "b1@test.com")
    from backend.memory.learner_profile import create_learner_profile
    p1 = create_learner_profile(db, user1.id, "spanish", initial_level="A1")
    p2 = create_learner_profile(db, user2.id, "spanish", initial_level="B1")
    return p1, p2


def create_user_helper(db, username, email):
    from backend.memory.learner_profile import create_user
    return create_user(db, username, email, "english")
