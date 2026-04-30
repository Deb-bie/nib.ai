"""
Text-to-Speech — gTTS integration.

Uses Google Text-to-Speech (gTTS)

Features:
    - Language-aware voice selection
    - Slow mode for difficult words (learner can request slower playback)
    - Audio caching — same text in same language won't be regenerated
    - Returns audio as bytes so the API can stream it to the frontend

Fallback: if gTTS fails (no internet), falls back to pyttsx3 (fully offline).
"""

import os
import hashlib
import logging
import tempfile
from pathlib import Path

from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

AUDIO_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/tutor_tts_cache"))
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Core TTS

def synthesise_speech(
    text: str,
    language_key: str,
    slow: bool = False,
    use_cache: bool = True,
) -> dict:
    """
    Convert text to speech audio bytes.

    Args:
        text:         the text to speak
        language_key: target language key e.g. "spanish", "french"
        slow:         if True, generate slower audio (good for tricky words)
        use_cache:    if True, reuse cached audio for identical text

    Returns:
        {
            "audio_bytes":   bytes,   — MP3 audio data
            "content_type":  str,     — "audio/mpeg"
            "language":      str,     — language code used
            "from_cache":    bool,
            "success":       bool,
            "error":         str | None,
        }
    """
    lang_config = SUPPORTED_LANGUAGES.get(language_key, {})
    tts_lang = lang_config.get("tts_voice", "en")

    # Check cache first
    if use_cache:
        cache_path = _get_cache_path(text, tts_lang, slow)
        if cache_path.exists():
            logger.debug(f"TTS cache hit for '{text[:40]}'")
            return {
                "audio_bytes": cache_path.read_bytes(),
                "content_type": "audio/mpeg",
                "language": tts_lang,
                "from_cache": True,
                "success": True,
                "error": None,
            }

    # Generate with gTTS
    try:
        audio_bytes = _gtts_generate(text, tts_lang, slow)

        # Save to cache
        if use_cache:
            cache_path = _get_cache_path(text, tts_lang, slow)
            cache_path.write_bytes(audio_bytes)

        logger.debug(f"TTS generated ({language_key}): '{text[:60]}'")
        return {
            "audio_bytes": audio_bytes,
            "content_type": "audio/mpeg",
            "language": tts_lang,
            "from_cache": False,
            "success": True,
            "error": None,
        }

    except Exception as gtts_err:
        logger.warning(f"gTTS failed: {gtts_err}. Trying pyttsx3 fallback...")

        # Offline fallback
        try:
            audio_bytes = _pyttsx3_generate(text)
            return {
                "audio_bytes": audio_bytes,
                "content_type": "audio/wav",
                "language": tts_lang,
                "from_cache": False,
                "success": True,
                "error": None,
            }
        except Exception as fallback_err:
            logger.error(f"TTS fallback also failed: {fallback_err}")
            return {
                "audio_bytes": b"",
                "content_type": "audio/mpeg",
                "language": tts_lang,
                "from_cache": False,
                "success": False,
                "error": str(gtts_err),
            }


def synthesise_word(word: str, language_key: str) -> dict:
    """
    Synthesise a single word with slow mode enabled.
    Used for pronunciation drills — learner hears word clearly.
    """
    return synthesise_speech(word, language_key, slow=True)


# Generators

def _gtts_generate(text: str, lang_code: str, slow: bool) -> bytes:
    """Generate audio using gTTS and return as bytes."""
    from gtts import gTTS # type: ignore

    tts = gTTS(text=text, lang=lang_code, slow=slow)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        tts.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _pyttsx3_generate(text: str) -> bytes:
    """
    Offline fallback TTS using pyttsx3.
    Lower quality but works with no internet.
    """
    import pyttsx3 # type: ignore
    import wave

    engine = pyttsx3.init()
    engine.setProperty("rate", 150)  # words per minute

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# Cache Helpers

def _get_cache_path(text: str, lang_code: str, slow: bool) -> Path:
    """Deterministic cache filename based on content hash."""
    key = f"{lang_code}_{slow}_{text}"
    file_hash = hashlib.md5(key.encode()).hexdigest()
    return AUDIO_CACHE_DIR / f"{file_hash}.mp3"


def clear_cache() -> int:
    """Remove all cached audio files. Returns number of files deleted."""
    count = 0
    for f in AUDIO_CACHE_DIR.glob("*.mp3"):
        f.unlink()
        count += 1
    logger.info(f"TTS cache cleared: {count} files removed")
    return count


def get_cache_size() -> dict:
    """Returns cache stats."""
    files = list(AUDIO_CACHE_DIR.glob("*.mp3"))
    total_bytes = sum(f.stat().st_size for f in files)
    return {
        "file_count": len(files),
        "total_mb": round(total_bytes / 1024 / 1024, 2),
    }