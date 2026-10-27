"""The pipeline as a LangGraph StateGraph.

    START -> ground -> [polish] -> human_gate -> produce -> verify -> END
                                       |                    ^    |
                                       +-> END (rejected)   +-fix+  (until clean or max_rounds)

Nodes read the contracts from .agentic-readme/ on disk instead of passing them in state,
so edits made to story.yaml while the graph is paused at the human gate are what produce
uses. verify and fix are the Evaluator-Optimizer loop, one pass per node visit.
"""

from __future__ import annotations

import operator
import uuid
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Optional, Tuple, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from rich.console import Console

from agentic_readme.core.models import FactsLedger, StorySpec, VerificationReport
from agentic_readme.core.runner import PipelineRunner, contract_path
from agentic_readme.core.tracing import configure_tracing
from agentic_readme.orchestrate.story_chain import polish_story
from agentic_readme.verify.optimizer import EvaluatorOptimizer


class ReadmeState(TypedDict, total=False):
    # Inputs
    repo_path: str
    audience: Optional[str]
    hook: Optional[str]
    polish: bool          # rewrite story prose with Claude before the gate
    review: bool          # pause at the human gate until someone approves
    max_rounds: int       # verify passes, as in EvaluatorOptimizer.run_loop
    # Written by nodes
    approved: bool
    round: int
    report: Dict[str, Any]
    passed: bool
    notes: Annotated[List[str], operator.add]  # each node appends one line


def _contracts(repo: Path) -> Tuple[StorySpec, FactsLedger]:
    return StorySpec.load_yaml(contract_path(repo, "story.yaml")), FactsLedger.load(contract_path(repo, "facts.json"))


def build_graph(llm: Optional[Any] = None, checkpointer: Optional[Any] = None, console: Optional[Console] = None):
    """Compile the graph. `llm` is only used by the polish node (default: Claude via llm.py)."""
    console = console or Console(stderr=True)

    def ground(state: ReadmeState) -> dict:
        runner = PipelineRunner(Path(state["repo_path"]), console=console)
        _, ledger = runner.phase_0_ground(target_audience=state.get("audience"), custom_hook=state.get("hook"))
        return {"round": 0, "notes": [f"ground: {len(ledger.facts)} facts recorded"]}

    def polish(state: ReadmeState) -> dict:
        repo = Path(state["repo_path"])
        story, ledger = _contracts(repo)
        polished, note = polish_story(story, ledger, llm=llm)
        if polished is not story:
            polished.save_yaml(contract_path(repo, "story.yaml"))
        console.print(f"[bold cyan][POLISH][/bold cyan] {note}")
        return {"notes": [f"polish: {note}"]}

    def human_gate(state: ReadmeState) -> dict:
        if not state.get("review"):
            return {"approved": True, "notes": ["human_gate: auto-approved"]}
        repo = Path(state["repo_path"])
        # Pauses the run; graph.invoke(Command(resume=<answer>), config) continues from here.
        answer = interrupt({
            "question": "Review story.yaml and facts.json, then approve to produce the README.",
            "story": str(contract_path(repo, "story.yaml")),
            "facts": str(contract_path(repo, "facts.json")),
        })
        approved = bool(answer)
        return {"approved": approved, "notes": [f"human_gate: {'approved' if approved else 'rejected'}"]}

    def produce(state: ReadmeState) -> dict:
        repo = Path(state["repo_path"])
        story, ledger = _contracts(repo)
        assets = PipelineRunner(repo, console=console).phase_1_produce(story, ledger)
        return {"notes": [f"produce: wrote {Path(assets['readme']).name} and assets/"]}

    def verify(state: ReadmeState) -> dict:
        repo = Path(state["repo_path"])
        story, ledger = _contracts(repo)
        report = EvaluatorOptimizer(repo, ledger).evaluate(repo / "README.md", story)
        rnd = state.get("round", 0) + 1
        console.print(f"[bold cyan][VERIFY round {rnd}][/bold cyan] {report.facts_checked} facts checked, "
                      f"{report.fatal_count} fatal, {report.warning_count} warnings")
        return {
            "round": rnd,
            "report": report.model_dump(mode="json"),
            "passed": report.fatal_count == 0,
            "notes": [f"verify: round {rnd}, {report.fatal_count} fatal, {report.warning_count} warnings"],
        }

    def fix(state: ReadmeState) -> dict:
        repo = Path(state["repo_path"])
        _, ledger = _contracts(repo)
        report = VerificationReport.model_validate(state["report"])
        EvaluatorOptimizer(repo, ledger).apply_fixes(repo / "README.md", report)
        return {"notes": [f"fix: applied auto-fixes after round {state['round']}"]}

    def after_ground(state: ReadmeState) -> str:
        return "polish" if state.get("polish") else "human_gate"

    def after_gate(state: ReadmeState) -> str:
        return "produce" if state.get("approved") else END

    def after_verify(state: ReadmeState) -> str:
        report = VerificationReport.model_validate(state["report"])
        # Same stopping rule as EvaluatorOptimizer.run_loop.
        if report.fatal_count == 0 and report.warning_count == 0:
            return END
        if state["round"] >= state.get("max_rounds", 2):
            return END
        return "fix"

    builder = StateGraph(ReadmeState)
    builder.add_node("ground", ground)
    builder.add_node("polish", polish)
    builder.add_node("human_gate", human_gate)
    builder.add_node("produce", produce)
    builder.add_node("verify", verify)
    builder.add_node("fix", fix)

    builder.add_edge(START, "ground")
    builder.add_conditional_edges("ground", after_ground, ["polish", "human_gate"])
    builder.add_edge("polish", "human_gate")
    builder.add_conditional_edges("human_gate", after_gate, ["produce", END])
    builder.add_edge("produce", "verify")
    builder.add_conditional_edges("verify", after_verify, ["fix", END])
    builder.add_edge("fix", "verify")

    # A checkpointer is what lets interrupt() pause a run and Command(resume=...) continue it.
    return builder.compile(checkpointer=checkpointer or InMemorySaver(), name="agentic-readme")


def run_graph(
    repo_path: Path,
    *,
    audience: Optional[str] = None,
    hook: Optional[str] = None,
    polish: bool = False,
    review: bool = False,
    approve: Optional[Callable[[Dict[str, Any]], bool]] = None,
    llm: Optional[Any] = None,
    max_rounds: int = 2,
    console: Optional[Console] = None,
) -> ReadmeState:
    """Run the graph to the end. At the human gate, `approve(payload)` decides (no callback: reject)."""
    configure_tracing()
    repo = Path(repo_path).resolve()
    graph = build_graph(llm=llm, console=console)
    config = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        # Shown on the LangSmith trace when tracing is on.
        "run_name": "agentic-readme",
        "tags": ["agentic-readme", "langgraph"],
        "metadata": {"repo": repo.name, "polish": polish, "review": review},
    }
    inputs: ReadmeState = {
        "repo_path": str(repo),
        "audience": audience,
        "hook": hook,
        "polish": polish,
        "review": review,
        "max_rounds": max_rounds,
    }

    state = graph.invoke(inputs, config)
    while state.get("__interrupt__"):
        payload = state["__interrupt__"][0].value
        state = graph.invoke(Command(resume=approve(payload) if approve else False), config)
    return state
