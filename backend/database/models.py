"""
Database models for the NiB.

Tables:
    users               — account info and native language
    learner_profiles    — one per user per target language (the learner model)
    skill_levels        — per-skill CEFR level for each learner profile
    sessions            — each tutoring session
    session_messages    — every message exchanged in a session
    errors              — every mistake made, tagged by type and concept
    vocabulary_items    — words the agent is tracking for this learner
    sr_reviews          — spaced repetition schedule per vocabulary item
    grammar_concepts    — grammar rules tracked for this learner
    curriculum_plans    — the agent's current teaching plan per learner
"""

from datetime import datetime
from sqlalchemy import ( # type: ignore
    Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base # type: ignore

Base = declarative_base()


# Users
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(50), unique=True, nullable=False)
    email           = Column(String(120), unique=True, nullable=False)
    password_hash   = Column(String(255), nullable=False)
    native_language = Column(String(30), nullable=False, default="english")
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    learner_profiles = relationship("LearnerProfile", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"


#  Learner Profile
class LearnerProfile(Base):
    """
    The core learner model. One per user per target language.
    This is what the agent reads before every session to understand
    who it's teaching and what they need.
    """
    __tablename__ = "learner_profiles"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    user_id               = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_language       = Column(String(30), nullable=False)
    overall_level         = Column(String(15), default="unassessed")
    learning_goal         = Column(String(200))
    preferred_style       = Column(String(50))
    sessions_completed    = Column(Integer, default=0)
    total_minutes_studied = Column(Integer, default=0)
    streak_days           = Column(Integer, default=0)
    last_session_at       = Column(DateTime, nullable=True)
    is_active             = Column(Boolean, default=True)
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user             = relationship("User", back_populates="learner_profiles")
    skill_levels     = relationship("SkillLevel", back_populates="learner_profile", cascade="all, delete-orphan")
    sessions         = relationship("Session", back_populates="learner_profile", cascade="all, delete-orphan")
    errors           = relationship("Error", back_populates="learner_profile", cascade="all, delete-orphan")
    vocabulary_items = relationship("VocabularyItem", back_populates="learner_profile", cascade="all, delete-orphan")
    grammar_concepts = relationship("GrammarConcept", back_populates="learner_profile", cascade="all, delete-orphan")
    curriculum_plans = relationship("CurriculumPlan", back_populates="learner_profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LearnerProfile user_id={self.user_id} language={self.target_language} level={self.overall_level}>"




# Skill Levels 

class SkillLevel(Base):
    """
    Tracks CEFR level per skill (vocabulary, grammar, speaking, etc.)
    for a given learner profile. Lets the agent teach different skills
    at different levels — a learner might be B1 in grammar but A2 in speaking.
    """
    __tablename__ = "skill_levels"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    skill              = Column(String(30), nullable=False)
    level              = Column(String(5), default="A1")
    score              = Column(Float, default=0.0)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="skill_levels")

    def __repr__(self):
        return f"<SkillLevel skill={self.skill} level={self.level} score={self.score}>"




# Sessions 

class Session(Base):
    """
    One tutoring session. The agent writes a summary and performance
    data here when the session ends — used by the curriculum planner
    to decide what to do next time.
    """
    __tablename__ = "sessions"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id    = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    started_at            = Column(DateTime, default=datetime.utcnow)
    ended_at              = Column(DateTime, nullable=True)
    duration_minutes      = Column(Float, default=0.0)
    session_type          = Column(String(30), default="mixed")
    planned_focus         = Column(JSON)    
    actual_focus          = Column(JSON)  
    performance_score     = Column(Float, nullable=True) 
    errors_made           = Column(Integer, default=0)
    exercises_completed   = Column(Integer, default=0)
    exercises_correct     = Column(Integer, default=0)
    agent_summary         = Column(Text, nullable=True)
    agent_notes           = Column(Text, nullable=True) 
    input_mode            = Column(String(10), default="text")  

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="sessions")
    messages        = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan")
    errors          = relationship("Error", back_populates="session")

    def __repr__(self):
        return f"<Session id={self.id} profile_id={self.learner_profile_id} score={self.performance_score}>"




# Session Messages

class SessionMessage(Base):
    """
    Every message exchanged in a session — both user and tutor.
    Used to reconstruct conversation history for the LLM context window.
    """
    __tablename__ = "session_messages"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role         = Column(String(10), nullable=False)
    content      = Column(Text, nullable=False)     
    audio_path   = Column(String(255), nullable=True)  
    timestamp    = Column(DateTime, default=datetime.utcnow)
    contains_error = Column(Boolean, default=False) 

    # Relationships
    session = relationship("Session", back_populates="messages")

    def __repr__(self):
        return f"<SessionMessage role={self.role} session_id={self.session_id}>"





# Errors 

class Error(Base):
    """
    Every mistake the learner makes, tagged by type and concept.
    The agent uses this to detect recurring patterns and trigger
    strategy switches when the same error appears 3+ times.
    """
    __tablename__ = "errors"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    session_id         = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    category           = Column(String(50), nullable=False)  
    concept            = Column(String(100), nullable=False)  
    user_input         = Column(Text, nullable=False)  
    correct_form       = Column(Text, nullable=False)  
    explanation        = Column(Text, nullable=True) 
    occurrence_count   = Column(Integer, default=1)
    strategy_switched  = Column(Boolean, default=False)
    resolved           = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=datetime.utcnow)
    last_seen_at       = Column(DateTime, default=datetime.utcnow)

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="errors")
    session         = relationship("Session", back_populates="errors")

    def __repr__(self):
        return f"<Error category={self.category} concept={self.concept} count={self.occurrence_count}>"




# Vocabulary Items

class VocabularyItem(Base):
    """
    Words and phrases the agent is tracking for this learner.
    Each item has a spaced repetition schedule attached.
    """
    __tablename__ = "vocabulary_items"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    word               = Column(String(100), nullable=False) 
    translation        = Column(String(100), nullable=False)
    example_sentence   = Column(Text, nullable=True)
    cefr_level         = Column(String(5), default="A1")
    times_seen         = Column(Integer, default=0)
    times_correct      = Column(Integer, default=0)
    mastered           = Column(Boolean, default=False)
    introduced_at      = Column(DateTime, default=datetime.utcnow)

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="vocabulary_items")
    sr_review       = relationship("SRReview", back_populates="vocabulary_item", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VocabularyItem word={self.word} mastered={self.mastered}>"




# Spaced Repetition Reviews

class SRReview(Base):
    """
    SM-2 spaced repetition state for each vocabulary item.
    The agent checks this at the start of every session to decide
    what needs reviewing today.
    """
    __tablename__ = "sr_reviews"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    vocabulary_item_id  = Column(Integer, ForeignKey("vocabulary_items.id"), nullable=False)
    easiness_factor     = Column(Float, default=2.5) 
    interval_days       = Column(Integer, default=1) 
    repetitions         = Column(Integer, default=0) 
    next_review_date    = Column(DateTime, default=datetime.utcnow)
    last_reviewed_at    = Column(DateTime, nullable=True)
    last_quality        = Column(Integer, nullable=True)

    # Relationships
    vocabulary_item = relationship("VocabularyItem", back_populates="sr_review")

    def __repr__(self):
        return f"<SRReview vocab_id={self.vocabulary_item_id} next={self.next_review_date} interval={self.interval_days}d>"




# Grammar Concepts 

class GrammarConcept(Base):
    """
    Grammar rules the agent is tracking for this learner.
    Separate from vocabulary — grammar mastery is tracked differently.
    """
    __tablename__ = "grammar_concepts"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    concept_key        = Column(String(100), nullable=False) 
    concept_name       = Column(String(150), nullable=False)
    cefr_level         = Column(String(5), default="A1")
    introduced         = Column(Boolean, default=False)  
    mastered           = Column(Boolean, default=False)
    mastery_score      = Column(Float, default=0.0)
    times_practiced    = Column(Integer, default=0)
    times_correct      = Column(Integer, default=0)
    teaching_strategy  = Column(String(50), default="drills") 
    strategy_switched_at = Column(DateTime, nullable=True) 
    introduced_at      = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="grammar_concepts")

    def __repr__(self):
        return f"<GrammarConcept concept={self.concept_key} mastered={self.mastered} strategy={self.teaching_strategy}>"




# Curriculum Plan 

class CurriculumPlan(Base):
    """
    The agent's current teaching plan for a learner.
    Created/updated by the curriculum planner after every session.
    This is what makes the agent's decisions visible and explainable.
    """
    __tablename__ = "curriculum_plans"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    learner_profile_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False)
    created_at         = Column(DateTime, default=datetime.utcnow)
    is_current         = Column(Boolean, default=True)

    # What the agent decided and why — stored as JSON for flexibility
    session_focus      = Column(JSON) 
    priority_concepts  = Column(JSON)
    concepts_to_skip   = Column(JSON)
    review_items       = Column(JSON) 
    agent_reasoning    = Column(Text) 
    detected_issues    = Column(JSON) 
    strategy_overrides = Column(JSON) 

    # Relationships
    learner_profile = relationship("LearnerProfile", back_populates="curriculum_plans")

    def __repr__(self):
        return f"<CurriculumPlan profile_id={self.learner_profile_id} created={self.created_at}>"