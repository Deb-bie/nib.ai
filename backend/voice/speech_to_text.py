"""
Speech-to-Text — Whisper integration.

Model size tradeoffs:
    tiny   — fastest, least accurate  (~39MB)
    base   — good balance             (~74MB)  ← recommended for dev
    small  — better accuracy          (~244MB)
    medium — near-human accuracy      (~769MB) ← recommended for demo
    large  — best accuracy            (~1.5GB)

Set WHISPER_MODEL in .env to control which model is loaded.
"""

import io
import os
import logging
import tempfile
import math
from pathlib import Path

import numpy as np # type: ignore

from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

_whisper_model = None

WHISPER_SAMPLE_RATE = 16_000


# Model loader

def _get_model():
    """Load and cache the Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None:
        import whisper # type: ignore
        model_name = os.getenv("WHISPER_MODEL", "base")
        logger.info(f"Loading Whisper model '{model_name}' — first load may take a moment…")
        _whisper_model = whisper.load_model(model_name)
        logger.info("Whisper model loaded successfully.")
    return _whisper_model


# Core transcription

def transcribe_audio(
    audio_bytes: bytes,
    language_key: str,
    audio_format: str = "webm",
) -> dict:
    """
    Transcribe raw audio bytes to text using Whisper.

    Args:
        audio_bytes:  raw audio data (WAV from the browser, after conversion)
        language_key: target language key e.g. "spanish", "french"
        audio_format: container format detected by the API route

    Returns:
        {
            "transcript":  str,
            "language":    str,
            "confidence":  float,   0.0–1.0
            "words":       list[dict],
            "success":     bool,
            "error":       str | None,
        }
    """
    lang_config = SUPPORTED_LANGUAGES.get(language_key, {})
    whisper_lang = lang_config.get("whisper_language", None)

    transcribe_options: dict = {
        "fp16": False, 
        "word_timestamps": True,
    }
    if whisper_lang:
        transcribe_options["language"] = whisper_lang

    try:
        model = _get_model()

        if audio_format == "wav":
            result = _transcribe_wav(model, audio_bytes, transcribe_options)
        else:
            result = _transcribe_via_tempfile(model, audio_bytes, audio_format, transcribe_options)

        transcript  = result["text"].strip()
        detected    = result.get("language", whisper_lang or "unknown")
        segments    = result.get("segments", [])

        if segments:
            avg_lp = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
            confidence = max(0.0, min(1.0, math.exp(avg_lp)))
        else:
            confidence = 0.0

        # Flatten word-level data
        words = [
            {
                "word":        w.get("word", "").strip(),
                "start":       round(w.get("start", 0), 2),
                "end":         round(w.get("end", 0), 2),
                "probability": round(w.get("probability", 0), 3),
            }
            for seg in segments
            for w in seg.get("words", [])
        ]

        logger.debug(
            f"Transcribed ({language_key}): '{transcript[:80]}' | "
            f"confidence={confidence:.2f}"
        )

        return {
            "transcript": transcript,
            "language":   detected,
            "confidence": round(confidence, 3),
            "words":      words,
            "success":    True,
            "error":      None,
        }

    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return {
            "transcript": "",
            "language":   whisper_lang or "unknown",
            "confidence": 0.0,
            "words":      [],
            "success":    False,
            "error":      str(e),
        }


# Transport implementations

def _transcribe_wav(model, wav_bytes: bytes, options: dict) -> dict:
    """
    Load WAV bytes with soundfile and call model.transcribe() with a numpy
    array.  Whisper accepts ndarray directly — no ffmpeg subprocess needed.
    """
    import soundfile as sf # type: ignore

    audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")

    if audio_data.ndim == 2:
        audio_data = audio_data.mean(axis=1)

    if sample_rate != WHISPER_SAMPLE_RATE:
        logger.debug(f"Resampling WAV from {sample_rate} Hz → {WHISPER_SAMPLE_RATE} Hz")
        audio_data = _resample(audio_data, sample_rate, WHISPER_SAMPLE_RATE)

    # Normalise to [-1, 1] just in case
    peak = np.abs(audio_data).max()
    if peak > 0:
        audio_data = audio_data / peak

    return model.transcribe(audio_data, **options)


def _transcribe_via_tempfile(model, audio_bytes: bytes, fmt: str, options: dict) -> dict:
    """
    Legacy path: write bytes to a temp file and let Whisper decode via ffmpeg.
    Only reached if the browser sends a non-WAV format (fallback scenario).
    """
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return model.transcribe(tmp_path, **options)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Linear-interpolation resample — good enough for speech, no extra deps.
    (The frontend sends 16 kHz so this is only a safety net.)
    """
    target_len = int(len(audio) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, target_len),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


# Convenience helpers

def transcribe_file(file_path: str, language_key: str) -> dict:
    """Convenience wrapper — transcribe directly from a file path."""
    path = Path(file_path)
    with open(path, "rb") as f:
        audio_bytes = f.read()
    return transcribe_audio(audio_bytes, language_key, audio_format=path.suffix.lstrip("."))


def is_confident(result: dict, threshold: float = 0.55) -> bool:
    """True if overall transcription confidence clears the threshold."""
    return result.get("confidence", 0.0) >= threshold


def get_uncertain_words(result: dict, threshold: float = 0.65) -> list[str]:
    """Words Whisper was uncertain about (low per-word probability)."""
    return [
        w["word"]
        for w in result.get("words", [])
        if w.get("probability", 1.0) < threshold
    ]
