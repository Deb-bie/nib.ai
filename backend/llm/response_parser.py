"""
Response parser — safely parses LLM output into structured Python objects.

"""

import json
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# JSON Parsing

def parse_json(raw: str) -> dict | list:
    """
    Parse a JSON string from LLM output.
    Handles markdown fences, leading/trailing text, and minor formatting issues.

    Raises:
        ValueError: if no valid JSON can be extracted
    """
    if not raw or not raw.strip():
        raise ValueError("Empty response from LLM")

    # 1. Try direct parse first (ideal case)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Extract first JSON object or array using regex
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not parse JSON from LLM response:\n{raw[:300]}")
    raise ValueError(f"Could not extract valid JSON from LLM response")


def parse_json_safe(raw: str, fallback: Any = None) -> Any:
    """Like parse_json but returns fallback instead of raising on failure."""
    try:
        return parse_json(raw)
    except (ValueError, Exception) as e:
        logger.warning(f"JSON parse failed, using fallback. Error: {e}")
        return fallback


# Field Extractors

def extract_field(data: dict, key: str, fallback: Any = None) -> Any:
    """Safe field extraction with fallback."""
    return data.get(key, fallback)


def extract_errors_from_response(raw: str) -> list[dict]:
    """
    Extract a list of errors from the session agent's response.
    Expected format:
    {
        "errors": [
            {
                "category": "verb_conjugation",
                "concept": "present_subjunctive",
                "user_input": "yo tengo",
                "correct_form": "yo tenga",
                "explanation": "..."
            }
        ]
    }
    """
    data = parse_json_safe(raw, fallback={"errors": []})
    return data.get("errors", [])


def extract_curriculum_plan(raw: str) -> dict:
    """
    Parse the curriculum planner's output.
    Returns a safe default plan if parsing fails.
    """
    default = {
        "session_focus": {"vocabulary": 40, "grammar": 40, "conversation": 20},
        "priority_concepts": [],
        "concepts_to_skip": [],
        "review_items": [],
        "agent_reasoning": "Default plan — could not parse agent response.",
        "detected_issues": [],
        "strategy_overrides": {},
    }
    data = parse_json_safe(raw, fallback=default)

    # Validate session_focus sums to ~100
    focus = data.get("session_focus", {})
    total = sum(focus.values()) if focus else 0
    if total == 0:
        data["session_focus"] = default["session_focus"]

    return {**default, **data}


def extract_assessment_result(raw: str) -> dict:
    """
    Parse the assessment agent's output.
    """
    default = {
        "overall_level": "A1",
        "skill_levels": {
            "vocabulary": "A1",
            "grammar": "A1",
            "reading": "A1",
            "writing": "A1",
            "speaking": "A1",
            "listening": "A1",
        },
        "reasoning": "",
        "recommended_focus": [],
    }
    data = parse_json_safe(raw, fallback=default)
    return {**default, **data}


def extract_session_evaluation(raw: str) -> dict:
    """
    Parse the session agent's end-of-session evaluation.
    """
    default = {
        "performance_score": 50.0,
        "errors": [],
        "exercises_completed": 0,
        "exercises_correct": 0,
        "summary": "",
        "notes_for_next_session": "",
        "skill_updates": {},
        "mastered_concepts": [],
    }
    data = parse_json_safe(raw, fallback=default)
    return {**default, **data}