"""Claude chat model for the optional LLM steps (story polish and the tool-calling agent).

Reads credentials the way the Anthropic SDK does (ANTHROPIC_API_KEY, or an `ant auth login`
profile). Set AGENTIC_README_MODEL to use a different Claude model.
"""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"

# Models that accept the server-side refusal fallback ("default" routes by refusal category).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def default_chat_model(model: Optional[str] = None, effort: str = DEFAULT_EFFORT):
    """Build a ChatAnthropic model. Thinking is adaptive; `effort` sets how much it spends."""
    from langchain_anthropic import ChatAnthropic

    model = model or os.getenv("AGENTIC_README_MODEL", DEFAULT_MODEL)
    kwargs = {}
    if model in FALLBACK_MODELS:
        # A refused request is re-run on a fallback model inside the same call.
        kwargs = {"betas": [FALLBACK_BETA], "model_kwargs": {"fallbacks": "default"}}
    return ChatAnthropic(model=model, max_tokens=16000, reasoning_effort=effort, **kwargs)
