"""
Thin Claude client wrapper with:
- The Recipe as a cached system prompt
- Automatic retry on rate limits / transient errors
- Streaming for large payloads
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from mabaan.config import LLM_MODEL, LLM_MAX_TOKENS, CACHE_ENABLED
from mabaan.recipe import RECIPE

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _build_system() -> list[dict[str, Any]]:
    if CACHE_ENABLED:
        return [{"type": "text", "text": RECIPE, "cache_control": {"type": "ephemeral"}}]
    return [{"type": "text", "text": RECIPE}]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(anthropic.RateLimitError),
    reraise=True,
)
def call(prompt: str, *, stream: bool = True) -> str:
    """Send a prompt to Claude with the Recipe as system prompt. Returns raw text."""
    client = get_client()
    system = _build_system()

    if stream:
        with client.messages.stream(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as s:
            msg = s.get_final_message()
    else:
        msg = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

    if msg.stop_reason == "refusal":
        raise ValueError(f"Model refused the request: {msg.stop_reason}")

    return next(b.text for b in msg.content if b.type == "text")


def call_json(prompt: str) -> dict[str, Any]:
    """Call Claude and parse the JSON envelope response."""
    raw = call(prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned non-JSON output: {e}\n---\n{raw[:500]}") from e
