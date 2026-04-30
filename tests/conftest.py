"""
Shared test fixtures.

Key fixture: mock_groq — replaces the real Groq API client with a deterministic stub so tests never make real API calls.
"""

import pytest # type: ignore
from sqlalchemy import create_engine # type: ignore
from sqlalchemy.orm import sessionmaker # type: ignore

from backend.database.models import Base
from backend.memory.learner_profile import create_user, create_learner_profile
from backend.database.seed_loader import seed_learner_profile # type: ignore


# In-memory test database
@pytest.fixture(scope="function")
def db():
    """Fresh in-memory SQLite DB for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)




# Clear in-memory agent state between tests 

@pytest.fixture(autouse=True)
def clear_active_sessions():
    """
    The orchestrator stores active sessions in module-level dicts.
    Clear them before each test so sessions don't leak between tests.
    """
    import backend.agent.orchestrator as orch_module
    orch_module._active_sessions.clear()
    orch_module._active_assessments.clear()
    yield
    orch_module._active_sessions.clear()
    orch_module._active_assessments.clear()



# Test user + profile 

@pytest.fixture
def test_user(db):
    return create_user(db, "testuser", "test@example.com", "english", "hashedpassword123")


@pytest.fixture
def test_profile(db, test_user):
    profile = create_learner_profile(
        db=db,
        user_id=test_user.id,
        target_language="spanish",
        learning_goal="conversational",
        initial_level="A1",
    )
    return profile


@pytest.fixture
def seeded_profile(db, test_user):
    """Profile with vocabulary and grammar already seeded."""
    profile = create_learner_profile(
        db=db,
        user_id=test_user.id,
        target_language="spanish",
        learning_goal="conversational",
        initial_level="A1",
    )
    seed_learner_profile(db, profile.id, "spanish", "A1")
    return profile


# Mock LLM

MOCK_SESSION_REPLY = "¡Hola! Vamos a practicar el español. ¿Cómo estás hoy?"

MOCK_CURRICULUM_PLAN = """{
    "session_focus": {"vocabulary": 40, "grammar": 40, "conversation": 20},
    "priority_concepts": [
        {"concept": "present_tense_regular", "skill": "grammar", "reason": "Foundation for all other tenses"}
    ],
    "concepts_to_skip": [],
    "review_items": [],
    "agent_reasoning": "Learner is at A1 — focusing on present tense and core vocabulary first.",
    "detected_issues": [],
    "strategy_overrides": {}
}"""

MOCK_SESSION_EVALUATION = """{
    "performance_score": 72.0,
    "errors": [
        {
            "category": "verb_conjugation",
            "concept": "present_tense_regular",
            "user_input": "yo hablar español",
            "correct_form": "yo hablo español",
            "explanation": "Use the conjugated form, not the infinitive"
        }
    ],
    "exercises_completed": 5,
    "exercises_correct": 4,
    "summary": "Good session with solid vocabulary work. One verb conjugation issue to address.",
    "notes_for_next_session": "Review present tense conjugation with more practice exercises.",
    "skill_updates": {"vocabulary": 5.0, "grammar": -2.0, "speaking": 3.0, "listening": 2.0},
    "mastered_concepts": []
}"""

MOCK_ASSESSMENT_RESULT = """{
    "overall_level": "A1",
    "skill_levels": {
        "vocabulary": "A1", "grammar": "A1", "reading": "A1",
        "writing": "A1", "speaking": "A1", "listening": "A1"
    },
    "reasoning": "Learner demonstrates basic vocabulary but struggles with conjugation.",
    "recommended_focus": ["present_tense_regular", "articles_gender"]
}"""


@pytest.fixture
def mock_groq(monkeypatch):
    """
    Replaces groq_client.chat() and related functions with deterministic stubs.
    Tests should never hit the real Groq API.
    """
    def fake_chat(messages, system_prompt="", **kwargs):
        all_text = system_prompt + " ".join(
            m.get("content", "") for m in (messages or [])
        )
        all_text_lower = all_text.lower()

        if kwargs.get("expect_json") or "JSON" in system_prompt.upper():
            if "session_focus" in all_text_lower or "curriculum" in all_text_lower:
                return MOCK_CURRICULUM_PLAN
            if "performance_score" in all_text_lower or "evaluating" in all_text_lower or "exercises_completed" in all_text_lower:
                return MOCK_SESSION_EVALUATION
            if "overall_level" in all_text_lower or "assessor" in all_text_lower or "skill_levels" in all_text_lower:
                return MOCK_ASSESSMENT_RESULT
        return MOCK_SESSION_REPLY

    def fake_chat_json(messages, system_prompt="", **kwargs):
        return fake_chat(messages, system_prompt, expect_json=True, **kwargs)

    def fake_single_turn(prompt, system_prompt="", **kwargs):
        return fake_chat([{"role": "user", "content": prompt}], system_prompt, **kwargs)

    def fake_single_turn_json(prompt, system_prompt="", **kwargs):
        return fake_chat_json([{"role": "user", "content": prompt}], system_prompt, **kwargs)


    def patch(module_path, attr, value):
        for prefix in ["backend.", ""]:
            full = f"{prefix}{module_path}"
            try:
                monkeypatch.setattr(f"{full}.{attr}", value)
            except (AttributeError, ModuleNotFoundError, Exception):
                pass

    patch("llm.groq_client", "chat",             fake_chat)
    patch("llm.groq_client", "chat_json",        fake_chat_json)
    patch("llm.groq_client", "single_turn",      fake_single_turn)
    patch("llm.groq_client", "single_turn_json", fake_single_turn_json)

    patch("agent.session_agent",     "chat",             fake_chat)
    patch("agent.session_agent",     "single_turn_json", fake_single_turn_json)
    patch("agent.curriculum_planner","single_turn_json", fake_single_turn_json)
    patch("agent.assessment_agent",  "chat",             fake_chat)
    patch("agent.assessment_agent",  "single_turn_json", fake_single_turn_json)

    return fake_chat
