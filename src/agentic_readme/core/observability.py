"""Tracing for every pipeline run, sent to LangSmith and Langfuse.

Both are built in. Each one turns on when its credentials are set and stays silent
(no network calls, no warnings) when they are not:

- LangSmith: LANGSMITH_TRACING=true and LANGSMITH_API_KEY (project: LANGSMITH_PROJECT)
- Langfuse:  LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY (host: LANGFUSE_BASE_URL,
             optional LANGFUSE_TRACING_ENVIRONMENT)

`trace_run` opens one trace per operation (readme-pipeline, readme-produce, ...) with an
explicit input and a short summary as output, and hands LangGraph / LangChain the config
that nests their runs under it. `traced` records a plain function as a typed step.
Everything sent to either platform first goes through `mask_secrets`.
"""

from __future__ import annotations

import functools
import inspect
import os
import re
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar

from langsmith import trace, traceable
from langsmith.run_helpers import get_tracing_context
from pydantic import BaseModel

from agentic_readme import __version__

DEFAULT_PROJECT = "agentic-readme"

F = TypeVar("F", bound=Callable[..., Any])


def langsmith_enabled() -> bool:
    flag = os.getenv("LANGSMITH_TRACING", "").strip().lower() == "true"
    return flag and bool(os.getenv("LANGSMITH_API_KEY"))


def langfuse_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and bool(os.getenv("LANGFUSE_SECRET_KEY"))


def enabled_backends() -> List[str]:
    return [name for name, on in (("LangSmith", langsmith_enabled()), ("Langfuse", langfuse_enabled())) if on]


# Masking. Traces carry repo paths, git remotes, CLI output, and the README itself, any of
# which can hold a token (e.g. https://x-access-token:...@github.com) or a local username.

_URL_CREDENTIALS = re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@")
_API_KEYS = re.compile(r"\b(?:sk-ant-|sk-lf-|pk-lf-|lsv2_|ghp_|gho_|ghs_|github_pat_|xox[abpr]-)[A-Za-z0-9_\-]+")
_HOME = re.compile(re.escape(str(Path.home())) + r"(?=/|\b)") if str(Path.home()) not in ("", "/") else None


def mask_text(text: str) -> str:
    text = _API_KEYS.sub("***", _URL_CREDENTIALS.sub("***@", text))
    return _HOME.sub("~", text) if _HOME else text


def mask_secrets(data: Any) -> Any:
    """Redact credentials in URLs, API keys, and the home directory from traced data."""
    if isinstance(data, str):
        return mask_text(data)
    if isinstance(data, BaseModel):
        return mask_secrets(data.model_dump(mode="json"))
    if isinstance(data, Path):
        return mask_text(str(data))
    if isinstance(data, dict):
        return {k: mask_secrets(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_secrets(v) for v in data]
    return data


def _langfuse_mask(*, data: Any, **kwargs: Any) -> Any:
    return mask_secrets(data)


@functools.lru_cache(maxsize=1)
def _init_langfuse() -> None:
    # Created once with masking and the release; get_client() (used by the LangChain
    # CallbackHandler too) then returns a client with the same settings.
    from langfuse import Langfuse

    Langfuse(mask=_langfuse_mask, release=__version__)


def langfuse_client():
    from langfuse import get_client

    _init_langfuse()
    return get_client()


@functools.lru_cache(maxsize=1)
def _langsmith_client():
    from langsmith import Client

    return Client(hide_inputs=mask_secrets, hide_outputs=mask_secrets)


# Never recorded as step inputs: the runner and its Console, models, and prebuilt chains.
_UNTRACED_ARGS = {"self", "console", "llm", "chain"}


def _default_inputs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in arguments.items() if k not in _UNTRACED_ARGS}


def traced(
    name: str,
    *,
    as_type: str = "chain",
    run_type: str = "chain",
    inputs: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Callable[[F], F]:
    """Record the decorated call as a LangSmith run and a Langfuse observation.

    as_type:  Langfuse observation type (chain, retriever, evaluator, tool, agent, ...)
    run_type: LangSmith run type (chain, tool, retriever, ...)
    inputs:   picks what is recorded as input from the call's arguments (default: all
              except self, console, llm, and chain)
    """
    select_inputs = inputs or _default_inputs

    def decorate(fn: F) -> F:
        signature = inspect.signature(fn)
        langsmith_fn = traceable(name=name, run_type=run_type, process_inputs=select_inputs)(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not langfuse_enabled():
                return langsmith_fn(*args, **kwargs)

            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            with langfuse_client().start_as_current_observation(
                name=name, as_type=as_type, input=select_inputs(dict(bound.arguments))
            ) as observation:
                result = langsmith_fn(*args, **kwargs)
                observation.update(output=result)
                return result

        return wrapper  # type: ignore[return-value]

    return decorate


class TracedRun:
    """Handle for one open trace: the LangChain config to invoke with, plus output and scores."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._langsmith_run: Any = None
        self._langfuse_root: Any = None

    def set_output(self, output: Dict[str, Any]) -> None:
        """The trace's output: a short summary, not the whole graph state."""
        if self._langsmith_run is not None:
            self._langsmith_run.end(outputs=output)
        if self._langfuse_root is not None:
            self._langfuse_root.update(output=output)

    def score(self, name: str, value: float, comment: Optional[str] = None) -> None:
        """Attach a quality score to the trace (Langfuse score, LangSmith feedback)."""
        if self._langfuse_root is not None:
            self._langfuse_root.score_trace(name=name, value=value, comment=comment)
        if self._langsmith_run is not None and langsmith_enabled():
            _langsmith_client().create_feedback(run_id=self._langsmith_run.id, key=name, score=value, comment=comment)


@contextmanager
def trace_run(
    name: str,
    *,
    inputs: Dict[str, Any],
    as_type: str = "chain",
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[TracedRun]:
    """Open one trace named `name` whose input is `inputs`.

    Pass `run.config` to graph.invoke / chain.invoke so LangGraph and LangChain runs nest
    under the trace, and call `run.set_output(...)` with a summary before leaving.
    """
    os.environ.setdefault("LANGSMITH_PROJECT", DEFAULT_PROJECT)
    tags = ["agentic-readme", *(tags or [])]
    metadata = {"app_version": __version__, **(metadata or {})}
    inputs = mask_secrets(inputs)
    run = TracedRun({"tags": tags, "metadata": metadata, "callbacks": []})

    with ExitStack() as stack:
        # LangSmith: a root run; LangChain's tracer nests the graph under it. A client set
        # by the caller's tracing_context wins over the masked default.
        client = None if get_tracing_context().get("client") or not langsmith_enabled() else _langsmith_client()
        run._langsmith_run = stack.enter_context(
            trace(name, run_type="chain", inputs=inputs, tags=tags, metadata=metadata, client=client)
        )

        # Langfuse: trace attributes first, then the root observation, then the handler
        # that turns LangGraph/LangChain callbacks into child observations.
        if langfuse_enabled():
            from langfuse import propagate_attributes
            from langfuse.langchain import CallbackHandler

            stack.enter_context(propagate_attributes(
                trace_name=name, tags=tags, version=__version__, metadata={k: str(v) for k, v in metadata.items()}
            ))
            run._langfuse_root = stack.enter_context(
                langfuse_client().start_as_current_observation(name=name, as_type=as_type, input=inputs)
            )
            run.config["callbacks"].append(CallbackHandler())

        yield run


def flush() -> None:
    """Send buffered traces. Call before a short-lived process (the CLI) exits."""
    if langsmith_enabled():
        from langchain_core.tracers.langchain import wait_for_all_tracers
        from langsmith.run_trees import get_cached_client

        wait_for_all_tracers()
        get_cached_client().flush()
        _langsmith_client().flush()
    if langfuse_enabled():
        langfuse_client().flush()
