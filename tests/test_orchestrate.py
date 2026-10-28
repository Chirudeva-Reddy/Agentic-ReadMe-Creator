"""Tests for the LangGraph pipeline, the LangChain layer, and LangSmith / Langfuse tracing.

No network: chat models are fakes, LangSmith runs go to an in-process recorder, and
Langfuse spans go to an in-memory OpenTelemetry exporter.
"""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langfuse import Langfuse
from langgraph.types import Command
from langsmith import Client
from langsmith.run_helpers import tracing_context
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rich.console import Console
from typer.testing import CliRunner

from agentic_readme.cli import app
from agentic_readme.core import observability
from agentic_readme.core.models import FactsLedger, FactSourceType, StorySpec
from agentic_readme.core.runner import PipelineRunner
from agentic_readme.mcp import TOOLS, execute_tool
from agentic_readme.orchestrate.evaluation import build_examples, langfuse_evaluator, reproduces_test_count, run_local_evaluation
from agentic_readme.orchestrate.graph import PRODUCERS, build_pipeline_graph, run_pipeline
from agentic_readme.orchestrate.llm import default_chat_model
from agentic_readme.orchestrate.story_chain import StoryProse, polish_story
from agentic_readme.orchestrate.tools import build_agent, build_tools
from agentic_readme.produce.writer_agent import WriterAgent

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
QUIET = Console(stderr=True, quiet=True)


def _sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_service"
    (repo / "src" / "sample_service").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "sample_service"\nversion = "1.0.0"\nrequires-python = ">=3.11"\n')
    (repo / "LICENSE").write_text("MIT License\nPermission is hereby granted...")
    (repo / "src" / "sample_service" / "__init__.py").write_text("")
    (repo / "src" / "sample_service" / "main.py").write_text("def run(): return 42\n")
    (repo / "tests" / "test_main.py").write_text("def test_one():\n    assert True\n\ndef test_two():\n    assert 2 == 2\n")
    return repo


def _story_and_ledger():
    ledger = FactsLedger(repo_name="demo")
    ledger.add_fact("test_count", 12, "tests/", FactSourceType.TEST_RUN)
    ledger.add_fact("license", "MIT", "LICENSE")
    story = StorySpec(repo_name="demo", target_audience="Developers", hook="Old hook.", problem="Old problem.", solution="Old solution.")
    return story, ledger


def _steps(state):
    return [note.split(":")[0] for note in state["notes"]]


class _StructuredFake:
    """Stands in for a chat model: with_structured_output returns a canned StoryProse."""

    def __init__(self, prose: StoryProse):
        self.prose = prose
        self.prompts = []

    def with_structured_output(self, schema, method=None):
        assert schema is StoryProse and method == "json_schema"
        return RunnableLambda(lambda prompt: self.prompts.append(prompt.to_string()) or self.prose)


class _ToolCallingFake(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class _RecordingClient(Client):
    """A LangSmith client that keeps runs in memory instead of uploading them."""

    def __init__(self):
        super().__init__(api_key="test", api_url="http://127.0.0.1:9", auto_batch_tracing=False)
        self.recorded = {}

    def create_run(self, name, inputs, run_type, *args, **kwargs):
        self.recorded[str(kwargs["id"])] = {"name": name, "parent": str(kwargs.get("parent_run_id"))}

    def update_run(self, *args, **kwargs):
        pass

    def parent_of(self, name):
        names = {run_id: run["name"] for run_id, run in self.recorded.items()}
        return next(names.get(run["parent"]) for run in self.recorded.values() if run["name"] == name)


# LangGraph pipeline

def test_pipeline_runs_producers_in_parallel(tmp_path):
    repo = _sample_repo(tmp_path)

    state = run_pipeline(repo, console=QUIET)

    assert state["passed"] is True and state["round"] == 1
    assert _steps(state)[:3] == ["ground", "human_gate", "produce"]
    assert sorted(_steps(state)[3:7]) == ["demo", "diagrams", "readme", "video"]
    assert _steps(state)[7:] == ["evaluate"]
    assert set(state["assets"]) == {"diagrams", "demo", "video", "readme"}
    assert "tests-2%20passed" in (repo / "README.md").read_text()

    edges = {(e.source, e.target) for e in build_pipeline_graph().get_graph().edges}
    assert all(("produce", p) in edges and (p, "evaluate") in edges for p in PRODUCERS)


def test_human_gate_pauses_and_uses_edited_story(tmp_path):
    repo = _sample_repo(tmp_path)
    graph = build_pipeline_graph(console=QUIET)
    config = {"configurable": {"thread_id": "review-1"}}

    paused = graph.invoke({"repo_path": str(repo), "output_dir": str(repo), "review": True}, config)
    assert paused["__interrupt__"][0].value["story"].endswith("story.yaml")
    assert not (repo / "README.md").exists()

    story_file = repo / ".agentic-readme" / "story.yaml"
    StorySpec.load_yaml(story_file).model_copy(update={"hook": "Edited at the human gate."}).save_yaml(story_file)

    done = graph.invoke(Command(resume=True), config)
    assert done["passed"] is True
    assert "Edited at the human gate." in (repo / "README.md").read_text()


def test_rejected_gate_stops_before_produce(tmp_path):
    repo = _sample_repo(tmp_path)
    result = PipelineRunner(repo, console=QUIET).run_all(auto_approve_gate=False, approve=lambda payload: False)
    assert result["approved"] is False and result["verification_report"] is None
    assert not (repo / "README.md").exists()


def test_fix_loop_repairs_drift(tmp_path, monkeypatch):
    repo = _sample_repo(tmp_path)
    write = WriterAgent.produce

    def write_with_drift(self, story, ledger):
        readme = write(self, story, ledger)
        readme.write_text(readme.read_text().replace("tests-2%20passed", "tests-40%20passed"))
        return readme

    monkeypatch.setattr(WriterAgent, "produce", write_with_drift)
    state = run_pipeline(repo, console=QUIET)

    assert _steps(state)[-3:] == ["evaluate", "fix", "evaluate"]
    assert state["round"] == 2 and state["passed"] is True
    assert "tests-2%20passed" in (repo / "README.md").read_text()


def test_runner_phases_run_on_graphs(tmp_path):
    repo = _sample_repo(tmp_path)
    runner = PipelineRunner(repo, console=QUIET)
    story, ledger = runner.phase_0_ground()

    assets = runner.phase_1_produce(story, ledger)
    report, passed = runner.phase_2_verify(story, ledger)

    assert set(assets) == {"diagrams", "demo", "video", "readme"}
    assert Path(assets["readme"]) == repo / "README.md"
    assert passed is True and report.fatal_count == 0


# LangSmith and Langfuse tracing

def test_tracing_is_silent_without_credentials(monkeypatch):
    for var in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("langfuse.get_client", lambda *a, **k: pytest.fail("Langfuse was called without credentials"))

    @observability.traced("double")
    def double(x):
        return 2 * x

    assert double(21) == 42
    assert observability.enabled_backends() == []
    with observability.trace_run("demo", inputs={"x": 1}) as run:
        assert run.config["callbacks"] == [] and run.config["tags"] == ["agentic-readme"]
        run.set_output({"ok": True})
        run.score("verification_passed", 1.0)


def test_mask_secrets():
    home = str(Path.home())
    story = StorySpec(repo_name="r", target_audience="a", hook="key lsv2_pt_abc123", problem="p", solution="s")
    masked = observability.mask_secrets({
        "remote": "https://x-access-token:ghs_secret@github.com/o/r.git",
        "keys": ["sk-lf-1234", "pk-lf-5678", "sk-ant-api03-xyz"],
        "path": Path(home) / "project",
        "story": story,
    })
    assert masked["remote"] == "https://***@github.com/o/r.git"
    assert masked["keys"] == ["***", "***", "***"]
    assert masked["path"] == "~/project" or home in ("", "/")
    assert masked["story"]["hook"] == "key ***"


def test_langsmith_trace_tree(tmp_path):
    repo = _sample_repo(tmp_path)
    client = _RecordingClient()

    with tracing_context(enabled=True, client=client):
        run_pipeline(repo, console=QUIET)

    assert client.parent_of("readme-pipeline") is None
    assert client.parent_of("pipeline-graph") == "readme-pipeline"
    assert client.parent_of("ground_contracts") == "ground"
    assert client.parent_of("evaluate_readme") == "evaluate"
    assert all(client.parent_of(p) == "pipeline-graph" for p in PRODUCERS)


_LANGFUSE_KEYS = {"LANGFUSE_PUBLIC_KEY": "pk-lf-test", "LANGFUSE_SECRET_KEY": "sk-lf-test", "LANGFUSE_BASE_URL": "http://127.0.0.1:9"}
_EXPORTER = InMemorySpanExporter()


@pytest.fixture
def langfuse_spans(monkeypatch):
    """Langfuse on, with spans kept in memory. The client is a per-process singleton, so it is
    created once, configured like observability's own (masking, release)."""
    for var, value in _LANGFUSE_KEYS.items():
        monkeypatch.setenv(var, value)
    client = Langfuse(public_key=_LANGFUSE_KEYS["LANGFUSE_PUBLIC_KEY"], secret_key=_LANGFUSE_KEYS["LANGFUSE_SECRET_KEY"],
                      base_url=_LANGFUSE_KEYS["LANGFUSE_BASE_URL"], span_exporter=_EXPORTER,
                      mask=observability._langfuse_mask, release="test")
    scores = []
    monkeypatch.setattr(observability.TracedRun, "score", lambda self, name, value, comment=None: scores.append((name, value)))
    _EXPORTER.clear()

    def finished():
        client.flush()
        spans = _EXPORTER.get_finished_spans()
        return spans, scores

    return finished


def _parent(spans, name):
    by_id = {s.context.span_id: s for s in spans}
    span = next(s for s in spans if s.name == name)
    return by_id[span.parent.span_id].name if span.parent else None


def test_langfuse_trace_tree(tmp_path, langfuse_spans):
    repo = _sample_repo(tmp_path)

    run_pipeline(repo, hook="Planted sk-lf-plantedsecret in the hook", console=QUIET)
    spans, scores = langfuse_spans()

    assert _parent(spans, "pipeline-graph") == "readme-pipeline"
    assert _parent(spans, "ground_contracts") == "ground"
    assert _parent(spans, "evaluate_readme") == "evaluate"
    assert all(_parent(spans, p) == "pipeline-graph" for p in PRODUCERS)

    types = {s.name: s.attributes.get("langfuse.observation.type") for s in spans}
    assert (types["readme-pipeline"], types["pipeline-graph"]) == ("chain", "chain")
    assert (types["ground_contracts"], types["evaluate_readme"]) == ("retriever", "evaluator")

    root = next(s for s in spans if s.name == "readme-pipeline")
    assert root.attributes["langfuse.trace.name"] == "readme-pipeline"
    assert "pipeline" in root.attributes["langfuse.trace.tags"]
    assert '"passed": true' in root.attributes["langfuse.observation.output"]
    assert scores == [("verification_passed", 1.0), ("fatal_findings", 0.0)]
    assert not any("plantedsecret" in str(v) for s in spans for v in s.attributes.values())


def test_review_run_is_one_trace(tmp_path, langfuse_spans):
    repo = _sample_repo(tmp_path)

    run_pipeline(repo, review=True, approve=lambda payload: True, console=QUIET)
    spans, _ = langfuse_spans()

    assert len({s.context.trace_id for s in spans}) == 1
    assert sum(s.name == "readme-pipeline" for s in spans) == 1


def test_claude_call_is_a_generation_with_model_and_usage(tmp_path, langfuse_spans, monkeypatch):
    # A stand-in for the Messages API, so the real ChatAnthropic request and response path runs.
    reply = {"hook": "Two tests, one function.", "problem": "Docs drift.", "solution": "It checks them."}

    class MessagesAPI(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            out = json.dumps({
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                "content": [{"type": "text", "text": json.dumps(reply)}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 120, "output_tokens": 30},
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), MessagesAPI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    llm = default_chat_model(anthropic_api_url=f"http://127.0.0.1:{server.server_port}", api_key="test")

    run_pipeline(_sample_repo(tmp_path), polish=True, llm=llm, console=QUIET)
    server.shutdown()
    spans, _ = langfuse_spans()

    generation = next(s for s in spans if s.attributes.get("langfuse.observation.type") == "generation")
    assert _parent(spans, "polish_story") == "polish"
    assert generation.attributes["langfuse.observation.model.name"] == "claude-opus-5-5"
    usage = json.loads(generation.attributes["langfuse.observation.usage_details"])
    assert (usage["input"], usage["output"]) == (120, 30)


# LangChain chain

def test_polish_story_accepts_grounded_rewrite():
    story, ledger = _story_and_ledger()
    fake = _StructuredFake(StoryProse(hook="Ship 12 tested functions.", problem="Docs drift.", solution="demo checks them."))

    polished, note = polish_story(story, ledger, llm=fake)

    assert note == "rewrote hook, problem, and solution"
    assert polished.hook == "Ship 12 tested functions."
    assert "- test_count: 12" in fake.prompts[0]  # facts reach the prompt
    assert story.hook == "Old hook."  # input story is not mutated


@pytest.mark.parametrize("prose, reason", [
    (StoryProse(hook="Backed by 99 tests.", problem="p", solution="s"), "numbers not in facts.json (99)"),
    (StoryProse(hook="A revolutionary tool.", problem="p", solution="s"), "flagged words (revolutionary)"),
])
def test_polish_story_rejects_ungrounded_rewrites(prose, reason):
    story, ledger = _story_and_ledger()
    polished, note = polish_story(story, ledger, llm=_StructuredFake(prose))
    assert polished is story
    assert reason in note


def test_polish_story_keeps_story_when_model_fails():
    story, ledger = _story_and_ledger()

    def boom(_):
        raise RuntimeError("no credentials")

    polished, note = polish_story(story, ledger, chain=RunnableLambda(boom))
    assert polished is story
    assert "RuntimeError: no credentials" in note


def test_pipeline_polish_node_rewrites_story(tmp_path):
    repo = _sample_repo(tmp_path)
    fake = _StructuredFake(StoryProse(hook="Two tests, one function.", problem="Docs drift.", solution="It checks them."))

    state = run_pipeline(repo, polish=True, llm=fake, console=QUIET)

    assert _steps(state)[:2] == ["ground", "polish"]
    assert StorySpec.load_yaml(repo / ".agentic-readme" / "story.yaml").hook == "Two tests, one function."


# LangChain tools and agent

def test_tools_mirror_mcp_specs(tmp_path):
    tools = build_tools()
    assert [t.name for t in tools] == [spec["name"] for spec in TOOLS]
    assert tools[0].invoke({"readme_path": str(tmp_path / "missing.md")}).startswith("Error: README file not found")


def test_agent_calls_audit_tool(tmp_path):
    repo = _sample_repo(tmp_path)
    PipelineRunner(repo, console=QUIET).run_all()
    readme = str(repo / "README.md")
    model = _ToolCallingFake(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "agentic_readme_audit", "args": {"readme_path": readme}, "id": "call_1"}]),
        AIMessage(content="The README passed."),
    ]))

    result = build_agent(model).invoke({"messages": [{"role": "user", "content": f"audit {readme}"}]})

    tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert "Audit Result: PASSED" in tool_message.content
    assert result["messages"][-1].content == "The README passed."


def test_mcp_run_without_auto_approve_stops_at_gate(tmp_path):
    repo = _sample_repo(tmp_path)
    result = execute_tool("agentic_readme_run", {"repo_path": str(repo), "auto_approve": False})
    assert result["isError"] is False
    assert "Stopped at the human gate" in result["content"][0]["text"]
    assert not (repo / "README.md").exists()


# Evaluation (local runner; the LangSmith and Langfuse runners share target and evaluators)

def test_local_evaluation_scores_an_example(tmp_path):
    shutil.copytree(EXAMPLES / "tip-splitter", tmp_path / "tip-splitter")

    assert build_examples(tmp_path) == [{"inputs": {"example": "tip-splitter"}, "outputs": {"test_count": 3}}]
    [result] = run_local_evaluation(tmp_path)
    assert result["scores"] == {"verification_passed": True, "first_pass_clean": True, "test_count_matches": True}
    # The target works on a temporary copy, so the example itself is untouched.
    assert (tmp_path / "tip-splitter" / "README.md").read_text() == (EXAMPLES / "tip-splitter" / "README.md").read_text()


def test_evaluators_score_mismatches_for_both_platforms():
    assert reproduces_test_count({"test_count": 3}, {"test_count": 4})["score"] is False
    evaluation = langfuse_evaluator(reproduces_test_count)(input={}, output={"test_count": 3}, expected_output={"test_count": 4})
    assert (evaluation.name, evaluation.value) == ("test_count_matches", 0.0)


# CLI

def test_cli_run_with_review(tmp_path):
    repo = _sample_repo(tmp_path)

    rejected = CliRunner().invoke(app, ["run", str(repo), "--review"], input="n\n")
    assert rejected.exit_code == 1 and "Stopped at the human gate" in rejected.output

    approved = CliRunner().invoke(app, ["run", str(repo), "--review"], input="y\n")
    assert approved.exit_code == 0, approved.output
    assert "0 fatal errors" in approved.output
