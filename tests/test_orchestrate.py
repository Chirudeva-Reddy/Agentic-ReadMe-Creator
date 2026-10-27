"""Tests for the LangChain / LangGraph / LangSmith layer (src/agentic_readme/orchestrate/).

No network: chat models are fakes, and LangSmith tracing stays off.
"""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.types import Command
from rich.console import Console
from typer.testing import CliRunner

from agentic_readme.cli import app
from agentic_readme.core.models import FactsLedger, FactSourceType, StorySpec
from agentic_readme.core.runner import PipelineRunner
from agentic_readme.core.tracing import traceable, tracing_enabled
from agentic_readme.mcp import TOOLS
from agentic_readme.orchestrate.evaluation import build_examples, reproduces_test_count, run_local_evaluation
from agentic_readme.orchestrate.graph import build_graph, run_graph
from agentic_readme.orchestrate.story_chain import StoryProse, polish_story
from agentic_readme.orchestrate.tools import build_agent, build_tools

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


# LangSmith tracing

def test_tracing_is_off_without_env(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    @traceable(name="double")
    def double(x):
        return 2 * x

    assert double(21) == 42
    assert tracing_enabled() is False


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


# LangChain tools and agent

def test_tools_mirror_mcp_specs(tmp_path):
    tools = build_tools()
    assert [t.name for t in tools] == [spec["name"] for spec in TOOLS]

    audit = tools[0]
    assert audit.invoke({"readme_path": str(tmp_path / "missing.md")}).startswith("Error: README file not found")


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


# LangGraph graph

def test_graph_runs_the_pipeline(tmp_path):
    repo = _sample_repo(tmp_path)

    state = run_graph(repo, console=QUIET)

    assert state["passed"] is True
    assert state["round"] == 1
    assert [n.split(":")[0] for n in state["notes"]] == ["ground", "human_gate", "produce", "verify"]
    assert "tests-2%20passed" in (repo / "README.md").read_text()


def test_graph_pauses_at_human_gate_and_uses_edited_story(tmp_path):
    repo = _sample_repo(tmp_path)
    graph = build_graph(console=QUIET)
    config = {"configurable": {"thread_id": "review-1"}}

    paused = graph.invoke({"repo_path": str(repo), "review": True}, config)
    assert paused["__interrupt__"][0].value["story"].endswith("story.yaml")
    assert not (repo / "README.md").exists()

    story_file = repo / ".agentic-readme" / "story.yaml"
    story = StorySpec.load_yaml(story_file)
    story.model_copy(update={"hook": "Edited at the human gate."}).save_yaml(story_file)

    done = graph.invoke(Command(resume=True), config)
    assert done["passed"] is True
    assert "Edited at the human gate." in (repo / "README.md").read_text()


def test_graph_stops_when_gate_is_rejected(tmp_path):
    repo = _sample_repo(tmp_path)
    state = run_graph(repo, review=True, approve=lambda payload: False, console=QUIET)
    assert state["approved"] is False
    assert not (repo / "README.md").exists()


def test_graph_fix_loop_repairs_drift(tmp_path, monkeypatch):
    repo = _sample_repo(tmp_path)
    produce = PipelineRunner.phase_1_produce

    def produce_with_drift(self, story, ledger):
        assets = produce(self, story, ledger)
        readme = Path(assets["readme"])
        readme.write_text(readme.read_text().replace("tests-2%20passed", "tests-40%20passed"))
        return assets

    monkeypatch.setattr(PipelineRunner, "phase_1_produce", produce_with_drift)
    state = run_graph(repo, console=QUIET)

    assert [n.split(":")[0] for n in state["notes"]][-3:] == ["verify", "fix", "verify"]
    assert state["round"] == 2 and state["passed"] is True
    assert "tests-2%20passed" in (repo / "README.md").read_text()


# LangSmith evaluation (run locally)

def test_local_evaluation_scores_an_example(tmp_path):
    shutil.copytree(EXAMPLES / "tip-splitter", tmp_path / "tip-splitter")

    assert build_examples(tmp_path) == [{"inputs": {"example": "tip-splitter"}, "outputs": {"test_count": 3}}]
    [result] = run_local_evaluation(tmp_path)
    assert result["scores"] == {"verification_passed": True, "first_pass_clean": True, "test_count_matches": True}
    # The target works on a temporary copy, so the example itself is untouched.
    assert (tmp_path / "tip-splitter" / "README.md").read_text() == (EXAMPLES / "tip-splitter" / "README.md").read_text()


def test_test_count_evaluator_flags_mismatch():
    assert reproduces_test_count({"test_count": 3}, {"test_count": 4})["score"] is False


# CLI

def test_cli_graph_command(tmp_path):
    repo = _sample_repo(tmp_path)
    result = CliRunner().invoke(app, ["graph", str(repo)])
    assert result.exit_code == 0, result.output
    assert "0 fatal errors" in result.output
