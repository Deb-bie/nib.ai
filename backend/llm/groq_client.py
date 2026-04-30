"""
Groq API client — single interface for all LLM calls in the system.
"""

import logging
from typing import Optional
from groq import Groq # type: ignore

from config import GROQ_API_KEY, GROQ_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)

# Client

_client: Optional[Groq] = None

def get_client() -> Groq:
    """Returns a singleton Groq client."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# Core Chat Call

def chat(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    expect_json: bool = False,
) -> str:
    """
    Send a chat completion request to Groq.

    Args:
        messages:      list of {"role": "user"/"assistant", "content": "..."}
        system_prompt: optional system message prepended to the conversation
        temperature:   0.0 = deterministic, 1.0 = creative
        max_tokens:    maximum response length
        expect_json:   if True, instructs the model to respond only in JSON

    Returns:
        The model's response as a plain string.
    """
    client = get_client()

    full_messages = []

    # Build system message
    if system_prompt:
        if expect_json:
            system_prompt += "\n\nIMPORTANT: Respond ONLY with valid JSON. No preamble, no markdown fences, no explanation outside the JSON object."
        full_messages.append({"role": "system", "content": system_prompt})

    full_messages.extend(messages)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        logger.debug(f"LLM response ({len(content)} chars): {content[:100]}...")
        return content

    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise


# Convenience Wrappers

def chat_json(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = LLM_MAX_TOKENS,
) -> str:
    """
    Like chat(), but signals the model to return pure JSON.
    Use response_parser.parse_json() on the result.
    Lower temperature by default for more reliable structure.
    """
    return chat(
        messages=messages,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        expect_json=True,
    )


def single_turn(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """Convenience wrapper for a single user message with no history."""
    return chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=system_prompt,
        **kwargs,
    )


def single_turn_json(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """single_turn but expecting JSON back."""
    return chat_json(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=system_prompt,
        **kwargs,
    )