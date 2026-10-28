"""The pipeline, built on LangGraph.

Every entry point (the CLI, the MCP server, PipelineRunner, and the LangChain tools) runs
one of these graphs:

    pipeline   START -> ground -> [polish] -> human_gate -> produce -> diagrams | demo | video | readme -> evaluate -> END
                                                  |                                                         ^   |
                                                  +-> END (rejected)                                        fix<+   (until clean or out of rounds)
    produce    START -> produce -> diagrams | demo | video | readme -> END
    verify     START -> evaluate <-> fix -> END

The four producers only read the locked contracts, so they run in parallel and the graph
waits for all of them before evaluating. State holds plain JSON values, which lets the
checkpointer save it while the run is paused at the human gate. The gate reads story.yaml
and facts.json from disk when it lets the run continue, so edits made during the pause
are what the producers use.
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

from agentic_readme.core.contracts import CONTRACTS_DIR, contract_path
from agentic_readme.core.models import (
    FactsLedger,
    FindingCategory,
    FindingSeverity,
    StorySpec,
    VerificationReport,
)
from agentic_readme.core.observability import trace_run, traced
from agentic_readme.ground.repo_analyst import RepoAnalyst
from agentic_readme.ground.story_builder import StoryBuilder, refresh_story
from agentic_readme.orchestrate.story_chain import polish_story
from agentic_readme.produce.demo_agent import DemoAgent
from agentic_readme.produce.diagram_agent import DiagramAgent
from agentic_readme.produce.video_agent import VideoAgent
from agentic_readme.produce.writer_agent import WriterAgent
from agentic_readme.verify.optimizer import EvaluatorOptimizer


def _merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {**left, **right}


class ReadmeState(TypedDict, total=False):
    # Inputs
    repo_path: str
    output_dir: str               # where contracts, README.md, and assets/ are written
    audience: Optional[str]
    hook: Optional[str]
    polish: bool                  # rewrite story prose with Claude before the gate
    review: bool                  # pause at the human gate until someone approves
    max_rounds: int               # evaluate passes, as in EvaluatorOptimizer.run_loop
    # Locked contracts as JSON: StorySpec / FactsLedger .model_dump(mode="json")
    story: Optional[Dict[str, Any]]
    facts: Dict[str, Any]
    # Written by nodes
    approved: bool
    assets: Annotated[Dict[str, Any], _merge]   # each producer adds its own key
    round: int
    report: Dict[str, Any]
    passed: bool
    notes: Annotated[List[str], operator.add]   # each node appends one line


PRODUCERS = ("produce_diagrams", "produce_demo", "produce_video", "write_readme")


def _out(state: ReadmeState) -> Path:
    return Path(state["output_dir"])


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _contracts(state: ReadmeState) -> Tuple[Optional[StorySpec], FactsLedger]:
    story = StorySpec.model_validate(state["story"]) if state.get("story") else None
    return story, FactsLedger.model_validate(state["facts"])


def _missing_readme_report(readme_path: Path) -> VerificationReport:
    report = VerificationReport(passed=False)
    report.add_finding(
        category=FindingCategory.RENDER_ISSUE,
        severity=FindingSeverity.FATAL,
        message=f"Target README.md does not exist at {readme_path}. Generate README first or run produce.",
        location=str(readme_path),
        expected="Existing README.md",
        actual="File not found",
        suggested_fix="Run 'agentic-readme produce' or 'agentic-readme run' to generate README.md.",
    )
    return report


@traced("ground_contracts", as_type="retriever")  # looks facts up in the repo
def ground_contracts(
    repo_path: Path,
    output_dir: Path,
    target_audience: Optional[str] = None,
    custom_hook: Optional[str] = None,
    console: Optional[Console] = None,
) -> Tuple[StorySpec, FactsLedger]:
    """Phase 0: inspect the repo and write story.yaml and facts.json to output_dir/.agentic-readme/."""
    console = console or Console(stderr=True)
    console.print(f"[bold cyan][Phase 0: GROUND][/bold cyan] Analyzing repository at {repo_path}...")

    analysis = RepoAnalyst(repo_path).analyze()
    ledger = analysis.facts_ledger
    existing = contract_path(output_dir, "story.yaml")
    if existing.exists():
        story = refresh_story(StorySpec.load_yaml(existing), ledger, target_audience, custom_hook)
        console.print(f"[green]✔ Kept your edits to {existing.name}[/green] (numbers refreshed from facts)")
    else:
        story = StoryBuilder(analysis).build_story(target_audience=target_audience, custom_hook=custom_hook)

    story_file = Path(output_dir) / CONTRACTS_DIR / "story.yaml"
    facts_file = Path(output_dir) / CONTRACTS_DIR / "facts.json"
    story.save_yaml(story_file)
    ledger.save(facts_file)

    console.print("[green]✔ Locked contracts created:[/green]")
    console.print(f"  - Story Spec: [bold]{story_file}[/bold]")
    console.print(f"  - Facts Ledger: [bold]{facts_file}[/bold] ({len(ledger.facts)} facts recorded)")
    return story, ledger


class _Nodes:
    """Node functions, bound to the console they print to and the model polish uses."""

    def __init__(self, console: Optional[Console] = None, llm: Optional[Any] = None):
        self.console = console or Console(stderr=True)
        self.llm = llm

    def ground(self, state: ReadmeState) -> dict:
        _, ledger = ground_contracts(
            Path(state["repo_path"]), _out(state), state.get("audience"), state.get("hook"), console=self.console
        )
        return {"round": 0, "notes": [f"ground: {len(ledger.facts)} facts recorded"]}

    def polish(self, state: ReadmeState) -> dict:
        story_file = contract_path(_out(state), "story.yaml")
        story = StorySpec.load_yaml(story_file)
        ledger = FactsLedger.load(contract_path(_out(state), "facts.json"))
        polished, note = polish_story(story, ledger, llm=self.llm)
        if polished is not story:
            polished.save_yaml(story_file)
        self.console.print(f"[bold cyan][POLISH][/bold cyan] {note}")
        return {"notes": [f"polish: {note}"]}

    def human_gate(self, state: ReadmeState) -> dict:
        story_file = contract_path(_out(state), "story.yaml")
        facts_file = contract_path(_out(state), "facts.json")
        decision = "auto-approved"
        if state.get("review"):
            # Pauses the run; graph.invoke(Command(resume=<answer>), config) continues from here.
            answer = interrupt({
                "question": "Review story.yaml and facts.json, then approve to produce the README.",
                "story": str(story_file),
                "facts": str(facts_file),
            })
            if not answer:
                return {"approved": False, "notes": ["human_gate: rejected"]}
            decision = "approved"
        # Read the contracts now, after any edits made during the pause.
        story, ledger = StorySpec.load_yaml(story_file), FactsLedger.load(facts_file)
        return {
            "approved": True,
            "story": story.model_dump(mode="json"),
            "facts": ledger.model_dump(mode="json"),
            "notes": [f"human_gate: {decision}"],
        }

    def produce(self, state: ReadmeState) -> dict:
        self.console.print("[bold cyan][Phase 1: PRODUCE][/bold cyan] Generating assets from locked story & facts...")
        return {"notes": ["produce: fanned out to diagrams, demo, video, readme"]}

    def producer(self, key: str, agent_cls: type, done: str) -> Callable[[ReadmeState], dict]:
        def node(state: ReadmeState) -> dict:
            story, ledger = _contracts(state)
            result = agent_cls(_out(state)).produce(story, ledger)
            self.console.print(f"  [green]✔ {done}[/green]")
            return {"assets": {key: _jsonable(result)}, "notes": [f"{key}: done"]}

        node.__name__ = f"produce_{key}"
        return node

    def evaluate(self, state: ReadmeState) -> dict:
        story, ledger = _contracts(state)
        readme = _out(state) / "README.md"
        rnd = state.get("round", 0) + 1
        if readme.exists():
            report = EvaluatorOptimizer(_out(state), ledger).evaluate(readme, story)
        else:
            report = _missing_readme_report(readme)
        self.console.print(
            f"[bold cyan][Phase 2: VERIFY round {rnd}][/bold cyan] {report.facts_checked} facts checked, "
            f"{report.fatal_count} fatal, {report.warning_count} warnings"
        )
        return {
            "round": rnd,
            "report": report.model_dump(mode="json"),
            "passed": report.fatal_count == 0,
            "notes": [f"evaluate: round {rnd}, {report.fatal_count} fatal, {report.warning_count} warnings"],
        }

    def fix(self, state: ReadmeState) -> dict:
        _, ledger = _contracts(state)
        report = VerificationReport.model_validate(state["report"])
        EvaluatorOptimizer(_out(state), ledger).apply_fixes(_out(state) / "README.md", report)
        return {"notes": [f"fix: applied auto-fixes after round {state['round']}"]}


def route_after_ground(state: ReadmeState) -> str:
    return "polish" if state.get("polish") else "human_gate"


def route_after_gate(state: ReadmeState) -> str:
    return "produce" if state.get("approved") else END


def route_after_evaluate(state: ReadmeState) -> str:
    report = VerificationReport.model_validate(state["report"])
    # Same stopping rule as EvaluatorOptimizer.run_loop; nothing to fix without a README.
    if report.fatal_count == 0 and report.warning_count == 0:
        return END
    if state["round"] >= state.get("max_rounds", 2) or not (_out(state) / "README.md").exists():
        return END
    return "fix"


def _add_produce(builder: StateGraph, nodes: _Nodes) -> None:
    builder.add_node("produce", nodes.produce)
    builder.add_node("produce_diagrams", nodes.producer("diagrams", DiagramAgent, "Diagram Agent: generated .excalidraw + light/dark SVGs"))
    builder.add_node("produce_demo", nodes.producer("demo", DemoAgent, "Demo Agent: generated VHS script + hero asset"))
    builder.add_node("produce_video", nodes.producer("video", VideoAgent, "Video Agent: generated /brag 20s spec + scene table"))
    builder.add_node("write_readme", nodes.producer("readme", WriterAgent, "Writer Agent: generated candidate README.md"))
    for name in PRODUCERS:
        builder.add_edge("produce", name)


def _add_verify(builder: StateGraph, nodes: _Nodes) -> None:
    builder.add_node("evaluate", nodes.evaluate)
    builder.add_node("fix", nodes.fix)
    builder.add_conditional_edges("evaluate", route_after_evaluate, ["fix", END])
    builder.add_edge("fix", "evaluate")


def build_pipeline_graph(llm: Optional[Any] = None, checkpointer: Optional[Any] = None, console: Optional[Console] = None):
    """The full pipeline. `llm` is only used by the polish node (default: Claude via llm.py)."""
    nodes = _Nodes(console, llm)
    builder = StateGraph(ReadmeState)
    builder.add_node("ground", nodes.ground)
    builder.add_node("polish", nodes.polish)
    builder.add_node("human_gate", nodes.human_gate)
    _add_produce(builder, nodes)
    _add_verify(builder, nodes)

    builder.add_edge(START, "ground")
    builder.add_conditional_edges("ground", route_after_ground, ["polish", "human_gate"])
    builder.add_edge("polish", "human_gate")
    builder.add_conditional_edges("human_gate", route_after_gate, ["produce", END])
    builder.add_edge(list(PRODUCERS), "evaluate")  # waits for all four producers

    # A checkpointer is what lets interrupt() pause a run and Command(resume=...) continue it.
    return builder.compile(checkpointer=checkpointer or InMemorySaver(), name="pipeline-graph")


def build_produce_graph(console: Optional[Console] = None):
    """Phase 1 alone: the four producers in parallel."""
    builder = StateGraph(ReadmeState)
    _add_produce(builder, _Nodes(console))
    builder.add_edge(START, "produce")
    builder.add_edge(list(PRODUCERS), END)
    return builder.compile(name="produce-graph")


def build_verify_graph(console: Optional[Console] = None):
    """Phase 2 alone: evaluate, auto-fix, and evaluate again until clean or out of rounds."""
    builder = StateGraph(ReadmeState)
    _add_verify(builder, _Nodes(console))
    builder.add_edge(START, "evaluate")
    return builder.compile(name="verify-graph")


def _summary(state: ReadmeState) -> Dict[str, Any]:
    """What a trace shows as output: the verdict and the steps taken, not the whole state."""
    summary: Dict[str, Any] = {
        "approved": state.get("approved", False),
        "passed": state.get("passed", False),
        "rounds": state.get("round", 0),
    }
    if state.get("report"):
        report = VerificationReport.model_validate(state["report"])
        summary.update(
            facts_checked=report.facts_checked,
            fatal_count=report.fatal_count,
            warning_count=report.warning_count,
            findings=[f"{f.severity.value}: {f.message}" for f in report.findings],
        )
    if state.get("assets"):
        summary["readme"] = state["assets"].get("readme")
    summary["steps"] = state.get("notes", [])
    return summary


def _score_verification(run: Any, state: ReadmeState) -> None:
    if state.get("report"):
        report = VerificationReport.model_validate(state["report"])
        run.score("verification_passed", 1.0 if state["passed"] else 0.0, comment=f"{report.fatal_count} fatal findings")
        run.score("fatal_findings", float(report.fatal_count))


def run_pipeline(
    repo_path: Path,
    *,
    output_dir: Optional[Path] = None,
    audience: Optional[str] = None,
    hook: Optional[str] = None,
    polish: bool = False,
    review: bool = False,
    approve: Optional[Callable[[Dict[str, Any]], bool]] = None,
    llm: Optional[Any] = None,
    max_rounds: int = 2,
    console: Optional[Console] = None,
) -> ReadmeState:
    """Run the full pipeline. At the human gate, `approve(payload)` decides (no callback: reject)."""
    repo = Path(repo_path).resolve()
    out = Path(output_dir or repo).resolve()
    graph = build_pipeline_graph(llm=llm, console=console)
    thread_id = str(uuid.uuid4())
    inputs: ReadmeState = {
        "repo_path": str(repo),
        "output_dir": str(out),
        "audience": audience,
        "hook": hook,
        "polish": polish,
        "review": review,
        "max_rounds": max_rounds,
    }
    trace_input = {"repo_path": str(repo), "audience": audience, "hook": hook, "polish": polish, "review": review}
    metadata = {"repo": repo.name, "polish": polish, "review": review}
    with trace_run("readme-pipeline", inputs=trace_input, tags=["pipeline"], metadata=metadata) as run:
        config = {**run.config, "configurable": {"thread_id": thread_id}}
        state = graph.invoke(inputs, config)
        # Resuming after the human gate stays inside the same trace.
        while state.get("__interrupt__"):
            payload = state["__interrupt__"][0].value
            state = graph.invoke(Command(resume=approve(payload) if approve else False), config)
        run.set_output(_summary(state))
        _score_verification(run, state)
    return state


def run_produce(output_dir: Path, story: StorySpec, ledger: FactsLedger, console: Optional[Console] = None) -> Dict[str, Any]:
    """Run Phase 1 on in-memory contracts; returns each producer's output paths."""
    out = Path(output_dir).resolve()
    inputs: ReadmeState = {"output_dir": str(out), "story": story.model_dump(mode="json"), "facts": ledger.model_dump(mode="json")}
    with trace_run("readme-produce", inputs={"output_dir": str(out)}, tags=["produce"], metadata={"repo": out.name}) as run:
        state = build_produce_graph(console).invoke(inputs, run.config)
        run.set_output(state["assets"])
    return state["assets"]


def run_verify(
    output_dir: Path,
    story: Optional[StorySpec],
    ledger: FactsLedger,
    max_rounds: int = 2,
    console: Optional[Console] = None,
) -> Tuple[VerificationReport, bool]:
    """Run Phase 2 on output_dir/README.md; returns the last report and whether it passed."""
    out = Path(output_dir).resolve()
    inputs: ReadmeState = {
        "output_dir": str(out),
        "story": story.model_dump(mode="json") if story else None,
        "facts": ledger.model_dump(mode="json"),
        "round": 0,
        "max_rounds": max_rounds,
    }
    trace_input = {"readme_path": str(out / "README.md"), "max_rounds": max_rounds}
    with trace_run("readme-verify", inputs=trace_input, tags=["verify"], metadata={"repo": out.name}) as run:
        state = build_verify_graph(console).invoke(inputs, run.config)
        run.set_output(_summary(state))
        _score_verification(run, state)
    return VerificationReport.model_validate(state["report"]), state["passed"]
