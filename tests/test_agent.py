"""Tests for agent/: the LangGraph tool loop, its guardrails, and the review pause.

No network: ScriptedModel replays fixed replies (including tool calls) in place of the LLM,
so each test checks what the graph and the tools do with those replies.
"""

import uuid
from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agentic_readme.agent.graph import describe_step, load_model, run_agent
from agentic_readme.agent.tools import make_tools, unknown_numbers
from agentic_readme.models import FactsLedger, StorySpec
from agentic_readme import pipeline


class ScriptedModel(GenericFakeChatModel):
    """A fake chat model that returns the given replies in order."""

    def bind_tools(self, tools, **kwargs):
        return self


def scripted(*replies) -> ScriptedModel:
    return ScriptedModel(messages=iter(replies))


def call(name: str, **args) -> AIMessage:
    """An agent reply that asks for one tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}])


def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "bill-splitter"
    (repo / "tests").mkdir(parents=True)
    (repo / "cli.py").write_text("import sys\nprint(sys.argv)\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT License", encoding="utf-8")
    (repo / "tests" / "test_cli.py").write_text("def test_a():\n    pass\n\ndef test_b():\n    pass\n", encoding="utf-8")
    return repo


def tool(repo: Path, name: str, review: bool = False):
    return {t.name: t for t in make_tools(repo, review)}[name]


def test_agent_tool_loop_rewrites_story_produces_and_passes(tmp_path: Path):
    repo = sample_repo(tmp_path)
    model = scripted(
        call("read_file", path="cli.py"),
        call("update_story", hook="Splitting a dinner bill should not need a calculator."),
        call("produce_readme"),
        call("verify_readme"),
        AIMessage(content="Rewrote the hook; verify passes."),
    )
    steps = []
    result = run_agent(repo, model, on_step=lambda update: steps.extend(describe_step(update)))

    assert result["passed"] is True
    assert result["checks"] == 1
    assert result["tool_calls"] == ["read_file", "update_story", "produce_readme", "verify_readme"]
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "<em>Splitting a dinner bill should not need a calculator.</em>" in readme
    assert "tests-2%20passed" in readme  # the number still comes from facts.json
    assert any(line.startswith("agent -> update_story(") for line in steps)
    assert "final check 1: PASSED" in steps


def test_final_check_sends_the_agent_back_until_verify_passes(tmp_path: Path):
    repo = sample_repo(tmp_path)
    model = scripted(
        AIMessage(content="Done."),         # stops without producing a README
        call("produce_readme"),              # ...is told why, and fixes it
        AIMessage(content="Done now."),
    )
    result = run_agent(repo, model)

    assert result["passed"] is True
    assert result["checks"] == 2
    feedback = [m for m in result["messages"] if isinstance(m, HumanMessage) and "final check failed" in m.content]
    assert len(feedback) == 1
    assert "README.md does not exist" in feedback[0].content


def test_final_check_gives_up_after_max_checks(tmp_path: Path):
    repo = sample_repo(tmp_path)
    result = run_agent(repo, scripted(AIMessage(content="Done."), AIMessage(content="Done.")), max_checks=2)
    assert result["passed"] is False
    assert result["checks"] == 2


def test_update_story_rejects_numbers_that_are_not_facts(tmp_path: Path):
    repo = sample_repo(tmp_path)
    pipeline.ground(repo)
    story_file = repo / ".agentic-readme" / "story.yaml"
    before = story_file.read_text(encoding="utf-8")

    rejected = tool(repo, "update_story").invoke({"hook": "Saves 40 hours a week."})
    assert rejected.startswith("Rejected: hook contains 40")
    assert story_file.read_text(encoding="utf-8") == before

    accepted = tool(repo, "update_story").invoke({"hook": "Two tests, both passing: 2 of 2."})
    assert accepted.startswith("Saved hook")
    assert StorySpec.load(story_file).hook == "Two tests, both passing: 2 of 2."


def test_unknown_numbers_ignores_digits_inside_words():
    facts = FactsLedger(repo_name="x")
    facts.add_fact("python_version", ">=3.11", "pyproject.toml")
    assert unknown_numbers("csv2json needs Python 3.11", facts) == []
    assert unknown_numbers("Python 3.12 and 7 tests", facts) == ["3.12", "7"]


def test_read_file_and_list_files_stay_inside_the_repo(tmp_path: Path):
    repo = sample_repo(tmp_path)
    (tmp_path / "secret.txt").write_text("password", encoding="utf-8")

    assert tool(repo, "read_file").invoke({"path": "../secret.txt"}).startswith("Error")
    assert "import sys" in tool(repo, "read_file").invoke({"path": "cli.py"})
    listing = tool(repo, "list_files").invoke({"folder": "."})
    assert "cli.py" in listing and "tests/test_cli.py" in listing
    assert tool(repo, "list_files").invoke({"folder": ".."}).startswith("Error")


def test_edit_readme_needs_one_exact_match_and_known_numbers(tmp_path: Path):
    repo = sample_repo(tmp_path)
    edit = tool(repo, "edit_readme")
    assert edit.invoke({"old_text": "a", "new_text": "b"}).startswith("Error: README.md doesn't exist")

    pipeline.run(repo)
    assert "appears 0 times" in edit.invoke({"old_text": "no such text", "new_text": "x"})
    assert "Rejected" in edit.invoke({"old_text": "## Quickstart", "new_text": "## Quickstart in 5 minutes"})
    assert edit.invoke({"old_text": "## Quickstart", "new_text": "## Try it"}).startswith("Edited")
    assert "## Try it" in (repo / "README.md").read_text(encoding="utf-8")


def test_review_pause_sends_feedback_to_the_agent_then_resumes(tmp_path: Path):
    repo = sample_repo(tmp_path)
    model = scripted(
        call("produce_readme"),                                  # pauses; the reviewer says no
        call("update_story", hook="Split a bill without arguing."),
        call("produce_readme"),                                  # pauses; the reviewer says yes
        AIMessage(content="Done."),
    )
    answers = iter(["no, the hook should mention arguing", "yes"])
    questions = []

    def reviewer(question: dict) -> str:
        questions.append(question)
        return next(answers)

    result = run_agent(repo, model, review=True, ask_human=reviewer)

    assert len(questions) == 2
    assert "hook:" in questions[0]["story"]
    rejection = [m for m in result["messages"] if isinstance(m, ToolMessage) and "did not approve" in m.content]
    assert "the hook should mention arguing" in rejection[0].content
    assert result["passed"] is True
    assert "<em>Split a bill without arguing.</em>" in (repo / "README.md").read_text(encoding="utf-8")


def test_tool_errors_become_messages_the_agent_can_read(tmp_path: Path):
    repo = sample_repo(tmp_path)
    model = scripted(call("no_such_tool"), call("produce_readme"), AIMessage(content="Done."))
    result = run_agent(repo, model)
    errors = [m.content for m in result["messages"] if isinstance(m, ToolMessage) and m.content.startswith("Error")]
    assert errors == ["Error: there is no tool named 'no_such_tool'."]
    assert result["passed"] is True


def test_load_model_sends_effort_and_refusal_fallback_to_claude(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    payload = load_model("anthropic:claude-opus-5-5")._get_request_payload([HumanMessage("hi")])
    assert payload["model"] == "claude-opus-5-5"
    assert payload["output_config"] == {"effort": "high"}
    assert payload["fallbacks"] == "default"
    assert payload["betas"] == ["server-side-fallback-2026-07-01"]


def test_eval_runs_the_agent_on_a_fresh_copy_and_grades_it():
    from agentic_readme.agent.evaluate import GRADERS, run_on_copy

    example = Path(__file__).resolve().parent.parent / "examples" / "tip-splitter"
    before = (example / "README.md").read_bytes()
    model = scripted(
        call("update_story", hook="Three friends, one bill, no calculator."),
        call("produce_readme"),
        AIMessage(content="Done."),
    )
    outputs = run_on_copy(example, model)

    assert (example / "README.md").read_bytes() == before  # the committed example is untouched
    assert outputs["hook"] == "Three friends, one bill, no calculator."
    assert outputs["tool_calls"] == ["update_story", "produce_readme"]
    scores = {grader.__name__: grader(outputs) for grader in GRADERS}
    assert scores == {"verify_passed": True, "fatal_findings": 0, "checks_used": 1, "story_numbers_grounded": True}


def test_eval_grader_catches_invented_numbers():
    from agentic_readme.agent.evaluate import story_numbers_grounded

    assert story_numbers_grounded({"invented_numbers": []}) is True
    assert story_numbers_grounded({"invented_numbers": ["40"]}) is False


def test_agent_command_prints_each_step(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    import agentic_readme.agent.graph as graph
    from agentic_readme.cli import app

    repo = sample_repo(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-used")
    monkeypatch.setattr(graph, "load_model", lambda name: scripted(call("produce_readme"), AIMessage(content="Done.")))

    result = CliRunner().invoke(app, ["agent", str(repo)])

    assert result.exit_code == 0, result.output
    assert "agent -> produce_readme()" in result.output
    assert "final check 1: PASSED" in result.output
    assert "Agent finished: PASSED after 1 tool calls" in result.output
