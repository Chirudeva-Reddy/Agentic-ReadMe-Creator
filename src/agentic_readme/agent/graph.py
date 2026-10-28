"""The agent: a LangGraph graph in which an LLM calls the pipeline's tools in a loop.

    START -> ground -> agent <-> tools            the tool-calling loop
                       agent -> final_check -> END, or back to agent with the findings

  ground       (code) runs pipeline.ground, then hands the agent the facts and the draft story
  agent        (LLM)  reads the conversation, then either calls tools or says it's done
  tools        (code) runs each tool call and gives the results back to the agent
  final_check  (code) runs verify. Pass -> END. Fail -> the findings go back to the agent,
               at most max_checks times. The model can't skip this step: it's an edge in
               the graph, not a tool the model may choose to call.

The state is the conversation (`messages`) plus two fields. After every step LangGraph
saves the state (the "checkpointer"); that is what lets produce_readme pause the whole run
for a human and resume it later.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated, Callable, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

from agentic_readme import pipeline
from agentic_readme.agent.tools import make_tools
from agentic_readme.models import FactsLedger, StorySpec

DEFAULT_MODEL = "anthropic:claude-opus-5-5"
MAX_GRAPH_STEPS = 80  # each tool round is two steps (agent + tools)

SYSTEM_PROMPT = """You write the README for a code repository.

The repository has already been inspected. facts.json holds every number we can prove, with
the file each one came from. story.yaml holds a first-draft story, and the README is generated
from it, so your main job is to improve the story's words until the README is clear and true.

Work in this order:
1. Look at the project with list_files and read_file (the entrypoint, sample data, tests,
   existing docs) until you know who it's for and what problem it solves.
2. Call update_story. The hook is one plain sentence naming a problem a stranger already has;
   it becomes the README's tagline. The problem and solution say what is painful today and
   what this project does about it, concretely, for the target audience.
3. Call produce_readme.
4. Call verify_readme. If it reports findings, fix them (edit_readme for README text, or
   update_story and then produce_readme again) and verify again.
5. When verify passes, stop calling tools and reply with a two-line summary of what you changed.

Rules:
- Use only numbers that are in facts.json; the tools reject any other number. Say other
  quantities in words.
- Describe only what you have seen in the code or its docs.
- No marketing words (revolutionary, seamless, robust, ...), greetings or filler."""


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # add_messages appends instead of replacing
    checks: int     # how many times final_check has run
    passed: bool    # did the last final_check pass?


def load_model(name: str) -> BaseChatModel:
    """Build a chat model from a "provider:model" name, e.g. "anthropic:claude-opus-5-5".

    For Claude we raise effort to "high" for multi-step tool use, and turn on Anthropic's
    server-side fallback, which retries a refused request on another model in the same call.
    """
    if name.startswith("anthropic:"):
        return init_chat_model(
            name,
            effort="high",
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            model_kwargs={"fallbacks": "default"},
        )
    return init_chat_model(name)


def _task(story: StorySpec, facts: FactsLedger) -> str:
    """The first message the agent sees: the facts it may use and the draft it should improve."""
    fact_lines = [f"- {key} = {fact.value}   (from {fact.source_file})" for key, fact in facts.facts.items()]
    claim_lines = [f"- {claim.claim}" for claim in story.key_claims]
    return "\n".join([
        f"Repository: {story.repo_name}",
        "",
        "facts.json (the only numbers you may use):",
        *fact_lines,
        "",
        "Draft story.yaml:",
        f"hook: {story.hook}",
        f"problem: {story.problem}",
        f"solution: {story.solution}",
        f"target_audience: {story.target_audience}",
        "claims (generated from facts.json, not editable):",
        *claim_lines,
        "",
        "Make the README clear and true, then stop.",
    ])


def build_graph(model: BaseChatModel, repo: Path, review: bool = False, max_checks: int = 3):
    repo = Path(repo).resolve()
    tools = make_tools(repo, review)
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)  # tells the model which tools exist

    def ground(state: AgentState) -> dict:
        story, facts = pipeline.ground(repo)
        return {"messages": [HumanMessage(_task(story, facts))], "checks": 0, "passed": False}

    def agent(state: AgentState) -> dict:
        reply = model_with_tools.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [reply]}

    def run_tools(state: AgentState) -> dict:
        """Run every tool call in the agent's last message; each result goes back as a ToolMessage."""
        results = []
        for call in state["messages"][-1].tool_calls:
            chosen = tools_by_name.get(call["name"])
            try:
                output = chosen.invoke(call["args"]) if chosen else f"Error: there is no tool named {call['name']!r}."
            except GraphInterrupt:
                raise  # the review pause must stop the graph, not become an error message
            except Exception as error:  # a bad argument becomes a message the agent can recover from
                output = f"Error: {error}"
            results.append(ToolMessage(content=str(output), tool_call_id=call["id"], name=call["name"]))
        return {"messages": results}

    def final_check(state: AgentState) -> dict:
        """The guardrail: the run only ends well if verify passes."""
        _story, facts = pipeline.load_contracts(repo)
        report, passed = pipeline.verify(repo, facts)
        checks = state["checks"] + 1
        if passed or checks >= max_checks:
            return {"checks": checks, "passed": passed}
        feedback = "\n".join([
            f"The final check failed ({report.fatal_count} fatal findings). Fix these with your tools, then stop:",
            *report.finding_lines(),
        ])
        return {"checks": checks, "passed": False, "messages": [HumanMessage(feedback)]}

    def after_agent(state: AgentState) -> str:
        return "tools" if state["messages"][-1].tool_calls else "final_check"

    def after_check(state: AgentState) -> str:
        return END if state["passed"] or state["checks"] >= max_checks else "agent"

    graph = StateGraph(AgentState)
    graph.add_node("ground", ground)
    graph.add_node("agent", agent)
    graph.add_node("tools", run_tools)
    graph.add_node("final_check", final_check)
    graph.add_edge(START, "ground")
    graph.add_edge("ground", "agent")
    graph.add_conditional_edges("agent", after_agent, ["tools", "final_check"])
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("final_check", after_check, ["agent", END])
    return graph.compile(checkpointer=InMemorySaver())


def run_agent(
    repo: Path,
    model: str | BaseChatModel | None = None,
    review: bool = False,
    max_checks: int = 3,
    ask_human: Callable[[dict], str] | None = None,
    on_step: Callable[[dict], None] | None = None,
) -> dict:
    """Run the graph to the end and return {"passed", "checks", "tool_calls", "messages"}.

    on_step(update) is called after each graph step (for printing progress). When review is
    on, ask_human(question) is called at the pause and its answer resumes the run.
    """
    if model is None:
        model = os.environ.get("AGENTIC_README_MODEL", DEFAULT_MODEL)
    if isinstance(model, str):
        model = load_model(model)
    repo = Path(repo).resolve()
    graph = build_graph(model, repo, review, max_checks)
    config = {
        "configurable": {"thread_id": str(uuid.uuid4())},  # which saved conversation to use
        "recursion_limit": MAX_GRAPH_STEPS,
        "run_name": "agentic-readme",                     # how the run is named in LangSmith
        "tags": ["agentic-readme"],
        "metadata": {"repo": repo.name},
    }

    next_input = {"messages": []}
    while True:
        for update in graph.stream(next_input, config, stream_mode="updates"):
            if on_step:
                on_step(update)
        paused = graph.get_state(config).interrupts
        if not paused:
            break
        answer = ask_human(paused[0].value) if ask_human else "yes"
        next_input = Command(resume=answer)  # continue from the pause with the human's answer

    state = graph.get_state(config).values
    tool_calls = [call["name"] for m in state["messages"] if isinstance(m, AIMessage) for call in m.tool_calls]
    return {"passed": state["passed"], "checks": state["checks"], "tool_calls": tool_calls, "messages": state["messages"]}


def describe_step(update: dict) -> list[str]:
    """Turn one graph step into short lines for the terminal."""
    lines = []
    for node, output in update.items():
        if node == "__interrupt__":
            lines.append("⏸ paused for review")
            continue
        for message in (output or {}).get("messages", []):
            if isinstance(message, AIMessage):
                if message.text.strip():
                    lines.append(f"agent: {message.text.strip()[:200]}")
                for call in message.tool_calls:
                    args = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in call["args"].items())
                    lines.append(f"agent -> {call['name']}({args})")
            elif isinstance(message, ToolMessage):
                first_line = str(message.content).strip().splitlines()[0] if str(message.content).strip() else ""
                lines.append(f"   {message.name}: {first_line[:160]}")
        if node == "final_check":
            verdict = "PASSED" if output.get("passed") else "FAILED"
            lines.append(f"final check {output.get('checks')}: {verdict}")
    return lines
