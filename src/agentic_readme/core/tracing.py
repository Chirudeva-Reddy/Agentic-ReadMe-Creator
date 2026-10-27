"""Optional LangSmith tracing for the pipeline.

Tracing is off unless LANGSMITH_TRACING=true and LANGSMITH_API_KEY are set, and the
`langsmith` package is only needed when it is on. Without it, `traceable` returns the
function unchanged, so the core pipeline keeps working with no extra dependencies.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, TypeVar

try:
    from langsmith import traceable as _traceable
except ImportError:  # the [langchain] extra is not installed
    _traceable = None

DEFAULT_PROJECT = "agentic-readme"

F = TypeVar("F", bound=Callable[..., Any])


def _drop_self(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Method traces would otherwise serialize the runner (and its Console) on every call.
    return {k: v for k, v in inputs.items() if k != "self"}


def traceable(name: str, run_type: str = "chain") -> Callable[[F], F]:
    """Record the decorated call as a LangSmith run when tracing is on."""
    if _traceable is None:
        return lambda fn: fn
    return _traceable(name=name, run_type=run_type, process_inputs=_drop_self)


def tracing_enabled() -> bool:
    """True when LangSmith will actually receive traces."""
    flag = os.getenv("LANGSMITH_TRACING", "").strip().lower() == "true"
    return flag and _traceable is not None and bool(os.getenv("LANGSMITH_API_KEY"))


def configure_tracing(project: str | None = None) -> bool:
    """Point traces at a LangSmith project (default: agentic-readme). Returns tracing_enabled()."""
    if project:
        os.environ["LANGSMITH_PROJECT"] = project
    else:
        os.environ.setdefault("LANGSMITH_PROJECT", DEFAULT_PROJECT)
    return tracing_enabled()
