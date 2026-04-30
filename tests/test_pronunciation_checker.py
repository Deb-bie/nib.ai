"""
Tests for the pronunciation checker.

All pure logic tests — no Whisper, no audio, no external calls.
"""

import pytest # type: ignore
from backend.voice.pronunciation_checker import (
    check_pronunciation,
    check_free_speech,
    _normalise,
    _similarity,
    _compare_words,
)


# Normalisation

class TestNormalise:

    def test_lowercases(self):
        assert _normalise("Hola Mundo") == ["hola", "mundo"]

    def test_strips_punctuation(self):
        assert _normalise("¡Hola! ¿Cómo estás?") == ["hola", "cómo", "estás"]

    def test_handles_empty(self):
        assert _normalise("") == []

    def test_preserves_accents(self):
        result = _normalise("está bien")
        assert "está" in result


# String similarity

class TestSimilarity:

    def test_identical_strings(self):
        assert _similarity("hola", "hola") == 1.0

    def test_completely_different(self):
        assert _similarity("cat", "xyz") < 0.5

    def test_close_typo(self):
        assert _similarity("mercado", "mercato") > 0.8

    def test_empty_strings(self):
        assert _similarity("", "hola") == 0.0
        assert _similarity("hola", "") == 0.0


# Word comparison

class TestCompareWords:

    def test_perfect_match(self):
        results = _compare_words(["hola", "mundo"], ["hola", "mundo"])
        assert all(r["match"] == "correct" for r in results)

    def test_missing_word(self):
        results = _compare_words(["hola", "mundo"], ["hola"])
        matches = {r["match"] for r in results}
        assert "missing" in matches

    def test_extra_word(self):
        results = _compare_words(["hola"], ["hola", "mundo"])
        matches = {r["match"] for r in results}
        assert "extra" in matches

    def test_wrong_word(self):
        results = _compare_words(["mercado"], ["mercato"])
        # Close but not exact — should be 'close' not 'wrong'
        assert results[0]["match"] in ("close", "wrong")

    def test_completely_wrong_word(self):
        results = _compare_words(["mercado"], ["perro"])
        assert results[0]["match"] == "wrong"


# check_pronunciation

class TestCheckPronunciation:

    def _make_transcription(self, text, confidence=0.85, words=None):
        return {
            "success": True,
            "transcript": text,
            "confidence": confidence,
            "words": words or [],
        }

    def test_perfect_pronunciation(self):
        result = check_pronunciation(
            expected_text="hola cómo estás",
            transcription_result=self._make_transcription("hola cómo estás"),
            language_key="spanish",
        )
        assert result["has_errors"] is False
        assert result["overall_accuracy"] == 1.0
        assert result["mispronounced_words"] == []

    def test_wrong_word_flagged(self):
        result = check_pronunciation(
            expected_text="buenos días",
            transcription_result=self._make_transcription("buenas noches"),
            language_key="spanish",
        )
        assert result["has_errors"] is True
        assert result["overall_accuracy"] < 1.0

    def test_failed_transcription_returns_gracefully(self):
        result = check_pronunciation(
            expected_text="hola",
            transcription_result={"success": False, "transcript": "", "confidence": 0},
            language_key="spanish",
        )
        assert result["has_errors"] is False
        assert "failed" in result["feedback"].lower() or "detected" in result["feedback"].lower()

    def test_uncertain_words_flagged(self):
        words_with_low_prob = [
            {"word": "mercado", "probability": 0.3, "start": 0, "end": 0.5},
        ]
        result = check_pronunciation(
            expected_text="mercado",
            transcription_result=self._make_transcription("mercado", words=words_with_low_prob),
            language_key="spanish",
        )
        assert result["uncertain_words"] == ["mercado"]

    def test_accuracy_partial_match(self):
        result = check_pronunciation(
            expected_text="yo tengo hambre",
            transcription_result=self._make_transcription("yo tengo pan"),
            language_key="spanish",
        )
        assert 0.0 < result["overall_accuracy"] < 1.0

    def test_feedback_string_is_non_empty(self):
        result = check_pronunciation(
            expected_text="hola",
            transcription_result=self._make_transcription("hola"),
            language_key="spanish",
        )
        assert isinstance(result["feedback"], str)
        assert len(result["feedback"]) > 0


# check_free_speech

class TestCheckFreeSpeech:

    def test_high_confidence_no_errors(self):
        result = check_free_speech(
            transcription_result={
                "success": True,
                "transcript": "hola cómo estás",
                "confidence": 0.9,
                "words": [
                    {"word": "hola", "probability": 0.95},
                    {"word": "cómo", "probability": 0.92},
                    {"word": "estás", "probability": 0.88},
                ],
            },
            language_key="spanish",
        )
        assert result["has_errors"] is False
        assert result["uncertain_words"] == []

    def test_low_confidence_words_flagged(self):
        result = check_free_speech(
            transcription_result={
                "success": True,
                "transcript": "yo quiero mercado",
                "confidence": 0.6,
                "words": [
                    {"word": "yo",      "probability": 0.95},
                    {"word": "quiero",  "probability": 0.88},
                    {"word": "mercado", "probability": 0.40},  # low
                ],
            },
            language_key="spanish",
        )
        assert result["has_errors"] is True
        assert "mercado" in result["uncertain_words"]

    def test_failed_transcription_handled(self):
        result = check_free_speech(
            transcription_result={"success": False, "transcript": "", "confidence": 0},
            language_key="spanish",
        )
        assert result["has_errors"] is False
