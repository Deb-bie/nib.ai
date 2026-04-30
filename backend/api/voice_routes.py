"""
Voice API routes.

POST /voice/transcribe          — audio → text (Whisper)
POST /voice/speak               — text → audio (gTTS)
POST /voice/speak/word          — single word TTS in slow mode
POST /voice/check-pronunciation — compare speech against expected text
POST /voice/session-message     — full pipeline: transcribe → session agent → speak
GET  /voice/cache/stats         — TTS cache stats
DELETE /voice/cache             — clear TTS cache
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form # type: ignore
from fastapi.responses import Response # type: ignore
from pydantic import BaseModel # type: ignore
from sqlalchemy.orm import Session # type: ignore

from database.db import get_db
from voice.speech_to_text import transcribe_audio, is_confident
from voice.text_to_speech import synthesise_speech, synthesise_word, get_cache_size, clear_cache
from voice.pronunciation_checker import check_pronunciation, check_free_speech
from agent.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Voice"])


# Request Models

BEGINNER_LEVELS = {"a1", "a2", "b1", "unassessed", ""}

def _level_slow(level: str) -> bool:
    """A1/A2/B1/unassessed → slow speech; B2+ → normal pace."""
    return level.strip().lower() in BEGINNER_LEVELS


def _clean_for_tts(text: str) -> str:
    """
    Strip content that should not be read aloud:
      - [CORRECTION]...[/CORRECTION] blocks (show written corrections only)
      - Bracket-style tags: [BEGIN SESSION], [PRACTICE MODE: ...], etc.
      - Common emojis used as visual markers: ❌ ✅ 📖 ⚠ 🎉 👏 💪 📚
    The remaining plain text is what the TTS engine will speak.
    """
    # Remove CORRECTION blocks entirely
    text = re.sub(r'\[CORRECTION\][\s\S]*?\[\/CORRECTION\]', '', text, flags=re.IGNORECASE)
    # Remove any remaining square-bracket tags  e.g. [BEGIN SESSION]
    text = re.sub(r'\[[^\]]{1,80}\]', '', text)
    # Strip visual-marker emojis
    text = re.sub(r'[❌✅📖⚠🎉👏💪📚🔴🟡🟢⭐🏆]', '', text)
    # Collapse extra whitespace/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


class SpeakRequest(BaseModel):
    text: str
    language_key: str
    slow: bool = False 
    learner_level: str = ""

class SpeakWordRequest(BaseModel):
    word: str
    language_key: str

class PronunciationCheckRequest(BaseModel):
    expected_text: str
    language_key: str
    transcript: str
    confidence: float
    words: list[dict] = []


# Transcription

@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language_key: str = Form(...),
):
    """
    Transcribe uploaded audio to text using Whisper.
    Accepts any audio format the browser's MediaRecorder produces (webm, ogg).
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Infer format from content type or filename
    content_type = audio.content_type or ""
    if "ogg" in content_type:
        fmt = "ogg"
    elif "wav" in content_type:
        fmt = "wav"
    elif "mp3" in content_type or "mpeg" in content_type:
        fmt = "mp3"
    else:
        fmt = "webm"   # default — Chrome MediaRecorder uses webm

    result = transcribe_audio(audio_bytes, language_key, audio_format=fmt)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {result['error']}")

    return {
        "success": True,
        "transcript": result["transcript"],
        "confidence": result["confidence"],
        "language": result["language"],
        "words": result["words"],
        "is_confident": is_confident(result),
    }


# Text-to-Speech

@router.post("/speak")
def speak(req: SpeakRequest):
    """
    Convert text to speech and return MP3 audio bytes.
    Frontend plays this directly in an <audio> element.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Clean the text before TTS (strip correction blocks, emojis, etc.)
    speak_text = _clean_for_tts(req.text)
    if not speak_text:
        raise HTTPException(status_code=400, detail="Nothing left to speak after cleaning")

    # learner_level takes precedence over explicit slow flag
    slow = _level_slow(req.learner_level) if req.learner_level else req.slow
    result = synthesise_speech(speak_text, req.language_key, slow=slow)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"TTS failed: {result['error']}")

    return Response(
        content=result["audio_bytes"],
        media_type=result["content_type"],
        headers={"X-From-Cache": str(result["from_cache"]).lower()},
    )


@router.post("/speak/word")
def speak_word(req: SpeakWordRequest):
    """
    Speak a single word in slow mode.
    Used for pronunciation drills.
    """
    result = synthesise_word(req.word, req.language_key)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"TTS failed: {result['error']}")

    return Response(
        content=result["audio_bytes"],
        media_type=result["content_type"],
    )


# Pronunciation Check

@router.post("/check-pronunciation")
def check_pronunciation_endpoint(req: PronunciationCheckRequest):
    """
    Check pronunciation by comparing expected text against a Whisper transcription.
    The frontend sends the transcription result it already received from /transcribe.
    """
    # Reconstruct the transcription result dict the checker expects
    transcription_result = {
        "success": True,
        "transcript": req.transcript,
        "confidence": req.confidence,
        "words": req.words,
    }

    result = check_pronunciation(
        expected_text=req.expected_text,
        transcription_result=transcription_result,
        language_key=req.language_key,
    )
    return {"success": True, **result}


# Full Voice Session Pipeline

@router.post("/session-message")
async def voice_session_message(
    audio: UploadFile = File(...),
    profile_id: int = Form(...),
    language_key: str = Form(...),
    learner_level: str = Form(default=""), 
    expected_text: str = Form(default=""), 
    db: Session = Depends(get_db),
):
    """
    Full voice pipeline in one endpoint:
        1. Transcribe audio (Whisper)
        2. Optionally check pronunciation
        3. Send transcript to session agent
        4. Convert agent reply to speech (gTTS)
        5. Return transcript + agent reply text + audio

    This is the main endpoint the session screen uses in voice mode.
    """
    # Step 1: Transcribe
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    content_type = audio.content_type or ""
    fmt = "ogg" if "ogg" in content_type else "wav" if "wav" in content_type else "webm"

    transcription = transcribe_audio(audio_bytes, language_key, audio_format=fmt)

    if not transcription["success"] or not transcription["transcript"]:
        raise HTTPException(
            status_code=422,
            detail="Could not transcribe audio. Please try speaking more clearly."
        )

    transcript = transcription["transcript"]

    # Step 2: Pronunciation check
    pronunciation_result = None
    if expected_text:
        pronunciation_result = check_pronunciation(
            expected_text=expected_text,
            transcription_result=transcription,
            language_key=language_key,
        )
    else:
        # Free speech — just flag uncertain words
        pronunciation_result = check_free_speech(transcription, language_key)

    # Step 3: Send to session agent
    try:
        orch = Orchestrator(db, profile_id)
        agent_reply = orch.send_message(transcript)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 4: Synthesise agent reply (speed matches learner level)
    # Strip correction blocks/markers before TTS so they aren't read aloud
    tts_text = _clean_for_tts(agent_reply)
    tts_result = synthesise_speech(tts_text or agent_reply, language_key, slow=_level_slow(learner_level))
    audio_b64 = None
    if tts_result["success"]:
        import base64
        audio_b64 = base64.b64encode(tts_result["audio_bytes"]).decode("utf-8")

    # Step 5: Return everything
    return {
        "success": True,
        "user_transcript": transcript,
        "transcription_confidence": transcription["confidence"],
        "pronunciation": pronunciation_result,
        "agent_reply": agent_reply,
        "agent_audio_b64": audio_b64,           # base64 MP3 — play directly in browser
        "agent_audio_content_type": "audio/mpeg",
    }


# Cache Management

@router.get("/cache/stats")
def cache_stats():
    return {"success": True, **get_cache_size()}


@router.delete("/cache")
def clear_tts_cache():
    count = clear_cache()
    return {"success": True, "files_deleted": count}