import os
from pathlib import Path
from dotenv import load_dotenv # type: ignore

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
LANGUAGES_DIR = DATA_DIR / "languages"

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# Supported Languages
SUPPORTED_LANGUAGES = {
    "spanish": {
        "name": "Spanish",
        "code": "es",
        "native_name": "Español",
        "tts_voice": "es",
        "whisper_language": "es",
    },
    "french": {
        "name": "French",
        "code": "fr",
        "native_name": "Français",
        "tts_voice": "fr",
        "whisper_language": "fr",
    },
    "german": {
        "name": "German",
        "code": "de",
        "native_name": "Deutsch",
        "tts_voice": "de",
        "whisper_language": "de",
    },
    "italian": {
        "name": "Italian",
        "code": "it",
        "native_name": "Italiano",
        "tts_voice": "it",
        "whisper_language": "it",
    }
}

# CEFR Proficiency Levels
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

CEFR_DESCRIPTIONS = {
    "A1": "Beginner — understands and uses basic familiar expressions",
    "A2": "Elementary — understands frequently used expressions",
    "B1": "Intermediate — can deal with most situations while travelling",
    "B2": "Upper Intermediate — can interact fluently with native speakers",
    "C1": "Advanced — can express ideas fluently and spontaneously",
    "C2": "Mastery — can understand virtually everything heard or read",
}

# Skills Tracked Per Learner
SKILL_TYPES = ["vocabulary", "grammar", "reading", "writing", "speaking", "listening"]

# Error Categories
ERROR_CATEGORIES = [
    "verb_conjugation",
    "noun_gender",
    "sentence_structure",
    "vocabulary_misuse",
    "pronunciation",
    "spelling",
    "article_usage",
    "tense_selection",
    "preposition_usage",
    "pronoun_usage",
]

# Spaced Repetition
SM2_DEFAULT_EASINESS = 2.5
SM2_MIN_EASINESS = 1.3 
SM2_INITIAL_INTERVAL_1 = 1 
SM2_INITIAL_INTERVAL_2 = 6 

# Session Settings
DEFAULT_SESSION_LENGTH_MINUTES = 10
MAX_ERRORS_BEFORE_STRATEGY_SWITCH = 3   # Same error this many times leads to a switch in approach
STAGNATION_SESSION_THRESHOLD = 3        # Sessions with no improvement = stagnation

# FastAPI
API_HOST = os.getenv("API_HOST")
API_PORT = int(os.getenv("API_PORT"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS").split(",")