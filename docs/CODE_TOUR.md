# Code tour

This page follows one real run through the code, file by file. It assumes you know basic Python (functions, classes, dictionaries, f-strings) and nothing else. Each library is explained the first time it appears.

For the big picture, read [ARCHITECTURE.md](ARCHITECTURE.md) first.

## The 30-second version

```text
agentic-readme agent examples/tip-splitter
        │
        ▼
ground        code   reads the repo, writes facts.json (numbers) + story.yaml (words)
agent ⇄ tools LLM    Claude reads files, rewrites the story's words, rebuilds and checks the README
final_check   code   runs verify; if it fails, the findings go back to Claude
        │
        ▼
README.md     every number in it came from facts.json
```

The Python package lives in `src/agentic_readme/`. Its `__init__.py` docstring lists every module in reading order.

---

## Follow one agent run

### 1. The command: `cli.py` → `agent()`

[Typer](https://typer.tiangolo.com/) turns each function decorated with `@app.command()` into a sub-command, and each argument into a command-line option. So `agentic-readme agent examples/tip-splitter --review` calls `agent(repo_path=Path("examples/tip-splitter"), review=True)`.

`agent()` checks that `ANTHROPIC_API_KEY` is set, then calls `run_agent` with two small functions: `print_step`, which prints progress, and `ask_human`, which asks you a question at the review pause.

### 2. Building the agent: `agent/graph.py` → `run_agent()` and `build_graph()`

`load_model("anthropic:claude-opus-5-5")` calls LangChain's `init_chat_model`, which returns a chat model object with an `.invoke(messages)` method. It works the same way for any provider, which is why the model is a plain string.

`build_graph` creates a **LangGraph `StateGraph`**. A graph is:

- a **state**: a dictionary every step can read (`AgentState`: `messages`, `checks`, `passed`)
- **nodes**: plain Python functions that take the state and return the fields they want to change
- **edges**: which node runs next. A *conditional edge* is a function that looks at the state and returns the next node's name.

```python
graph.add_edge(START, "ground")
graph.add_edge("ground", "agent")
graph.add_conditional_edges("agent", after_agent, ["tools", "final_check"])
graph.add_edge("tools", "agent")
graph.add_conditional_edges("final_check", after_check, ["agent", END])
```

`messages: Annotated[list[AnyMessage], add_messages]` means: when a node returns `{"messages": [new_message]}`, append it to the list instead of replacing the list. That's how the conversation grows.

`graph.compile(checkpointer=InMemorySaver())` turns the description into something runnable. The checkpointer saves the state after every step, so the run can pause and resume (step 7).

`run_agent` then calls `graph.stream(...)`, which runs node after node and yields what each one returned.

### 3. Node `ground` → `pipeline.ground()`

This step is deterministic: the same repo always gives the same files. In `pipeline.py`:

```python
project = detect_project(repo)                    # ground/project.py
facts = collect_facts(repo, project.entrypoints)  # ground/facts.py
story = build_story(project, facts, ...)          # ground/story.py (or refresh_story if story.yaml exists)
story.save(...); facts.save(...)                  # writes .agentic-readme/
```

- **`detect_project`** looks only at file names. `pyproject.toml` means Python, `cli.py` is the entrypoint, a `tests/` folder means `pytest`. It returns a `Project`, a `@dataclass`: a class whose fields are declared at the top, so Python writes `__init__` for you.
- **`collect_facts`** builds a `FactsLedger`, one helper per source: git, `pyproject.toml`, `package.json`, `Cargo.toml`, the license, the test count, benchmark JSON files, and integration files. It runs two commands with `subprocess.run`, both with a timeout: `pytest --collect-only`, which lists the tests without running them, and `python3 cli.py --help`. Each fact records the file it came from.
- **`build_story`** writes a first-draft `StorySpec`. Each claim is built from one fact, so it carries that fact's number and evidence file.

`FactsLedger` and `StorySpec` are in `models.py`. They're **pydantic** `BaseModel`s: classes with typed fields that pydantic checks, and that can be saved as JSON or YAML and loaded back.

The node then sends the agent its task as a `HumanMessage`: every fact it may use, and the draft story (`_task()`).

### 4. Node `agent`: the LLM's turn

```python
reply = model_with_tools.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
```

`model.bind_tools(tools)` sent Claude each tool's name, its arguments and its docstring. The reply is an `AIMessage`. It either contains text ("done"), or `tool_calls`, for example `[{"name": "update_story", "args": {"hook": "..."}, "id": "call_1"}]`. **The model never runs code itself.** It only asks.

`after_agent` routes the graph to `tools` if there are tool calls, and to `final_check` if not.

### 5. Node `tools` → `run_tools()` and `agent/tools.py`

```python
for call in state["messages"][-1].tool_calls:
    output = tools_by_name[call["name"]].invoke(call["args"])
    results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
```

That loop is all "tool calling" means. Each tool in `agent/tools.py` is a normal function with LangChain's `@tool` decorator, defined inside `make_tools(repo)` so it remembers which repo it works on (a *closure*). The guardrails are ordinary `if` statements:

- `update_story` loads `story.yaml`, calls `unknown_numbers(text, facts)`, and refuses to save if the new words contain a number that isn't in `facts.json`. The refusal is a normal return value, so the model reads it and tries again.
- `read_file` resolves the path and refuses anything outside the repo.
- `produce_readme` calls `pipeline.produce` (step 6).
- `verify_readme` calls `pipeline.verify` and returns every finding with its fix (`VerificationReport.finding_lines()`).

Then the graph goes back to `agent` with the results. This back-and-forth is the **ReAct loop**.

### 6. Inside the tools: `pipeline.produce()` and `pipeline.verify()`

`produce` calls four functions, each writing its own files:

| Function | Writes |
| :--- | :--- |
| `produce/diagram.py` → `draw_diagrams` | `assets/diagrams/`: Excalidraw JSON plus light, dark and static SVGs |
| `produce/demo.py` → `make_demo` | `assets/demo/`: a VHS script plus a drawn terminal SVG |
| `produce/video.py` → `make_storyboard` | `assets/video/`: a five-scene, 20-second storyboard |
| `produce/readme.py` → `write_readme` | `README.md`, from one f-string template |

`verify` is a small loop of its own:

```python
for round_number in range(1, max_rounds + 1):
    report = check(readme, facts)             # claims.py + rendering.py + voice.py
    if clean or round_number == max_rounds:
        break
    auto_fix(readme, facts, report)           # fixer.py
```

- `verify/claims.py` finds numbers in the README with regular expressions. For example, `tests-(\d+)` finds the test badge. Each one is compared with `facts.json`.
- `verify/rendering.py` checks the things GitHub breaks: `<video>` tags pointing at repo files, oversized GIFs, missing alt text, broken links, and SVGs GitHub would reject. It parses each SVG with `xml.etree.ElementTree`.
- `verify/voice.py` flags buzzwords and filler using the lists in `rules.py`.
- `verify/fixer.py` fixes what has one right answer, such as changing a wrong badge number to the fact's value.

### 7. The review pause (`--review`): `interrupt()`

With `--review`, `produce_readme` calls `interrupt({...story...})`. LangGraph stops the whole graph and saves its state. `run_agent` sees the pause (`graph.get_state(config).interrupts`), calls `ask_human`, and resumes with `graph.stream(Command(resume=answer), ...)`.

On resume, `interrupt()` returns your answer. A "yes" writes the README. Anything else goes back to the agent as feedback, and it revises the story. That's **human-in-the-loop**.

### 8. Node `final_check`: the guardrail

When Claude stops calling tools, `final_check` runs `pipeline.verify` itself. If verify passes, the graph ends. If not, the findings go back to Claude as a new message, and Claude gets another turn, up to `max_checks` times. Claude can't skip this step, because it's an edge in the graph rather than a tool. That's the **evaluator-optimizer** pattern: deterministic code grades, the LLM improves.

---

## The same job without an LLM

`agentic-readme run examples/tip-splitter` calls `pipeline.run`, which is `ground → produce → verify` with the draft story as written. Every step from 3 and 6 above runs; only Claude is missing. This is the path for CI and for anyone without an API key.

The MCP server (`mcp.py`) exposes the same steps to an outside agent such as Claude Desktop or Cursor. It reads one JSON-RPC message per line from stdin and writes one answer per line to stdout. `handle_request` routes by `method`, and `execute_tool` routes by tool name, through a dictionary of small handler functions.

---

## Every file, one line each

| File | What it does |
| :--- | :--- |
| `models.py` | Data shapes: facts, story, findings, report |
| `rules.py` | Word lists, patterns and size limits the checks use |
| `pipeline.py` | `ground`, `produce`, `check`, `verify`, `run` on one page |
| `ground/project.py` | Language, entrypoint, commands, diagram nodes |
| `ground/facts.py` | Every provable number, with its source |
| `ground/story.py` | First-draft story; refresh numbers in an edited story |
| `produce/readme.py` | README template |
| `produce/diagram.py` | Architecture diagram (Excalidraw + SVG) |
| `produce/demo.py` | VHS script + drawn terminal |
| `produce/video.py` | 20-second storyboard |
| `verify/claims.py` | Numbers vs facts, leaked jargon, badge links |
| `verify/rendering.py` | GitHub rendering rules |
| `verify/voice.py` | Wording and layout rules; `strip_slop` |
| `verify/fixer.py` | Fixes with one right answer |
| `agent/tools.py` | The six tools and their guardrails |
| `agent/graph.py` | The LangGraph graph, model setup, run loop |
| `agent/evaluate.py` | LangSmith experiment over `examples/` |
| `cli.py` | `agentic-readme` commands |
| `mcp.py` | MCP server for AI assistants |

## Try it yourself

Print the graph from the code:

```bash
python3 -c "from agentic_readme.agent.graph import build_graph; from langchain_core.language_models.fake_chat_models import GenericFakeChatModel as M; M.bind_tools = lambda self, tools: self; print(build_graph(M(messages=iter([])), '.').get_graph().draw_mermaid())"
```

Watch every step in LangSmith:

```bash
export LANGSMITH_TRACING=true LANGSMITH_API_KEY=... ANTHROPIC_API_KEY=...
```

```bash
agentic-readme agent examples/tip-splitter
```

Read `tests/test_agent.py` to see the whole graph driven by a scripted fake model, with no network and no key.

---

## Questions an interviewer might ask

**Where exactly is the "agent"?**
In `agent/graph.py`. Claude decides which tools to call, in what order, and what the story should say. Everything else is deterministic code it calls through tools. With the Claude Code skill or MCP, the outside assistant plays the same role.

**What stops it from making up numbers?**
Three layers. The model is only shown facts from `facts.json`. `update_story` and `edit_readme` reject any number that isn't in it. And `final_check` runs `verify`, which fails on any number that disagrees with `facts.json`. The model can't skip that, because it's a graph edge, not a tool.

**Why LangGraph instead of a `while` loop?**
The loop itself is small, and you can see it in `run_tools` and the edges. LangGraph adds the parts that are tedious to hand-write: saved state after every step, which makes the human pause and resume possible; a step limit; streaming each step; and tracing in LangSmith with no extra code.

**Why not let the LLM write the whole README?**
Words need judgment, but numbers need to be exact. Splitting the job lets each part do what it's good at, and makes the output testable: `tests/test_examples.py` requires byte-identical output from the deterministic part.

**How do you know the agent is any good?**
`agentic-readme eval` runs it on every example as a LangSmith experiment. Each run gets four scores: did verify pass, fatal findings remaining, checks used, and whether the story's numbers are grounded. Deterministic graders mean no LLM is judging another LLM, and you can compare models or prompts run by run.

**What happens when a tool fails?**
`run_tools` catches the exception and returns `Error: ...` as the tool's result. The model reads it and adjusts. Only the review pause (`GraphInterrupt`) is allowed through, because it must stop the graph.

**How does the human approval work?**
`interrupt()` inside `produce_readme` pauses the graph, and the checkpointer keeps the state. The CLI asks you, then `Command(resume=answer)` continues. A "no" with feedback becomes the tool's result, so the agent revises the story.

**What would you add next?**
Run `eval` across models and prompt versions and keep the best. Add an LLM-as-judge grader for hook quality, kept separate from the deterministic ones. Check the agent's README edits against the house-style rules before saving them, not only at verify time.
