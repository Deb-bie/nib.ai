"""
Pronunciation Checker.

Compares the Whisper transcript of what the learner said
against what they were supposed to say, and flags mismatches
as pronunciation errors.

Approach:
    We use Whisper's own transcription as the signal.
    If the learner said "mercado" but Whisper heard "mercato",
    that's a pronunciation flag — Whisper couldn't recognise it.

    We use two levels of comparison:
    1. Exact match   — word-for-word (strict)
    2. Fuzzy match   — edit distance (catches near-misses)

    We also use Whisper's per-word probability scores —
    words Whisper was uncertain about are pronunciation candidates.

"""

import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Main Checker

def check_pronunciation(
    expected_text: str,
    transcription_result: dict,
    language_key: str,
    strict: bool = False,
) -> dict:
    """
    Compare the expected text against what Whisper transcribed.

    Args:
        expected_text:        what the learner was supposed to say
        transcription_result: the dict returned by speech_to_text.transcribe_audio()
        language_key:         target language key
        strict:               if True, use exact matching; if False, use fuzzy

    Returns:
        {
            "has_errors":          bool,
            "overall_accuracy":    float,     — 0.0–1.0
            "word_results":        list[dict], — per-word comparison
            "mispronounced_words": list[str],  — words that were wrong
            "uncertain_words":     list[str],  — words Whisper was unsure about
            "transcript":          str,        — what Whisper actually heard
            "expected":            str,        — what they should have said
            "feedback":            str,        — human-readable feedback string
        }
    """
    if not transcription_result.get("success"):
        return _error_result(expected_text, "Transcription failed — could not analyse pronunciation.")

    transcript = transcription_result.get("transcript", "").strip()
    if not transcript:
        return _error_result(expected_text, "No speech detected.")

    # Normalise both strings for comparison
    expected_words = _normalise(expected_text)
    spoken_words = _normalise(transcript)

    # Word-level comparison
    word_results = _compare_words(expected_words, spoken_words)

    # Words Whisper itself was uncertain about (low probability)
    uncertain = _get_uncertain_words(transcription_result)

    # Compute accuracy
    correct = sum(1 for w in word_results if w["match"] == "correct")
    total = len(word_results)
    accuracy = correct / total if total > 0 else 0.0

    mispronounced = [
        w["expected"] for w in word_results
        if w["match"] in ("wrong", "missing") and w["expected"]
    ]

    has_errors = len(mispronounced) > 0 or len(uncertain) > 0

    feedback = _build_feedback(
        accuracy=accuracy,
        mispronounced=mispronounced,
        uncertain=uncertain,
        expected_text=expected_text,
        transcript=transcript,
    )

    return {
        "has_errors": has_errors,
        "overall_accuracy": round(accuracy, 3),
        "word_results": word_results,
        "mispronounced_words": mispronounced,
        "uncertain_words": uncertain,
        "transcript": transcript,
        "expected": expected_text,
        "feedback": feedback,
    }


def check_free_speech(
    transcription_result: dict,
    language_key: str,
) -> dict:
    """
    Check pronunciation quality for free-form speech (conversation mode)
    where there is no single "expected" text.

    Uses only Whisper's confidence scores — flags words with very low
    per-word probability as likely pronunciation issues.
    """
    if not transcription_result.get("success"):
        return {
            "has_errors": False,
            "uncertain_words": [],
            "transcript": "",
            "feedback": "Could not analyse speech.",
        }

    transcript = transcription_result.get("transcript", "")
    uncertain = _get_uncertain_words(transcription_result, threshold=0.55)

    return {
        "has_errors": len(uncertain) > 0,
        "uncertain_words": uncertain,
        "transcript": transcript,
        "feedback": (
            f"Possible pronunciation issues with: {', '.join(uncertain)}"
            if uncertain else
            "Pronunciation sounds clear!"
        ),
    }


# Word Comparison

def _compare_words(expected: list[str], spoken: list[str]) -> list[dict]:
    """
    Align expected words against spoken words using SequenceMatcher
    and classify each word as correct / wrong / missing / extra.
    """
    results = []
    matcher = SequenceMatcher(None, expected, spoken)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for exp, spk in zip(expected[i1:i2], spoken[j1:j2]):
                results.append({"expected": exp, "spoken": spk, "match": "correct"})

        elif tag == "replace":
            exp_chunk = expected[i1:i2]
            spk_chunk = spoken[j1:j2]
            # Pair them up as best we can
            for k in range(max(len(exp_chunk), len(spk_chunk))):
                exp_w = exp_chunk[k] if k < len(exp_chunk) else ""
                spk_w = spk_chunk[k] if k < len(spk_chunk) else ""
                similarity = _similarity(exp_w, spk_w)
                results.append({
                    "expected": exp_w,
                    "spoken": spk_w,
                    "match": "close" if similarity > 0.7 else "wrong",
                    "similarity": round(similarity, 2),
                })

        elif tag == "delete":
            for exp in expected[i1:i2]:
                results.append({"expected": exp, "spoken": "", "match": "missing"})

        elif tag == "insert":
            for spk in spoken[j1:j2]:
                results.append({"expected": "", "spoken": spk, "match": "extra"})

    return results


# Helpers

def _normalise(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    text = text.lower()
    text = re.sub(r"[^\w\s'-]", "", text)
    return [w for w in text.split() if w]


def _similarity(a: str, b: str) -> float:
    """0.0–1.0 string similarity using edit distance."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _get_uncertain_words(result: dict, threshold: float = 0.65) -> list[str]:
    """Words with Whisper per-word probability below the threshold."""
    return [
        w["word"]
        for w in result.get("words", [])
        if w.get("probability", 1.0) < threshold and w.get("word", "").strip()
    ]


def _build_feedback(
    accuracy: float,
    mispronounced: list[str],
    uncertain: list[str],
    expected_text: str,
    transcript: str,
) -> str:
    """Build a human-readable feedback string for the learner."""
    if accuracy >= 0.95 and not uncertain:
        return "Excellent pronunciation! Everything was clear."

    if accuracy >= 0.8:
        base = "Good job! "
    elif accuracy >= 0.6:
        base = "Getting there! "
    else:
        base = "Keep practising! "

    parts = []
    if mispronounced:
        words_str = ", ".join(f'"{w}"' for w in mispronounced[:3])
        parts.append(f"Focus on: {words_str}")
    if uncertain and not mispronounced:
        words_str = ", ".join(f'"{w}"' for w in uncertain[:3])
        parts.append(f"Try to speak these more clearly: {words_str}")

    if parts:
        return base + ". ".join(parts) + "."
    return base + "Try again for a cleaner take."


def _error_result(expected_text: str, message: str) -> dict:
    return {
        "has_errors": False,
        "overall_accuracy": 0.0,
        "word_results": [],
        "mispronounced_words": [],
        "uncertain_words": [],
        "transcript": "",
        "expected": expected_text,
        "feedback": message,
    }