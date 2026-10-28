# Evaluation

How we measure whether the agent writes good, true READMEs. The first part runs today. The second is the broader benchmark protocol it grows into.

---

## What runs today: `agentic-readme eval`

```bash
export ANTHROPIC_API_KEY=... LANGSMITH_API_KEY=...
```

```bash
agentic-readme eval                              # default model
```

```bash
agentic-readme eval --model anthropic:claude-sonnet-5-5   # compare another model
```

What it does (`src/agentic_readme/agent/evaluate.py`):

1. Creates the LangSmith dataset `agentic-readme-examples` if it doesn't exist, with one row per project in `examples/`.
2. For each row, copies the project to a temp folder and deletes its `README.md` and `story.yaml`, so the agent starts from nothing. Then it runs the full agent: ground, tool loop, final check.
3. Scores the run with **deterministic graders**, so no LLM judges another LLM:

| Grader | Measures | Good value |
| :--- | :--- | :--- |
| `verify_passed` | Did the agent's final check pass? | `true` |
| `fatal_findings` | Fatal findings in a fresh, read-only audit of the finished README | `0` |
| `checks_used` | How many final checks the agent needed | `1` |
| `story_numbers_grounded` | Is every number in the hook, problem, solution and audience also in `facts.json`? | `true` |

Each run appears in LangSmith as one experiment, named after the model. Every row links to its full trace: each LLM call, tool call and tool result. Comparing two experiments shows which model or prompt change helped, row by row.

The graders and the eval target are tested offline with a scripted model in `tests/test_agent.py`.

---

## Broader benchmark protocol (planned)

### Test set (~20 repositories)

- **Reference READMEs (5)**: `duet` (CLI evaluation tool), `body2health` (full-stack health metrics), `odoo-salon-erp` (Dockerized ERP), `ClaimLens` (computer-vision insurance triage), `NLP-Proj` (hallucination detection).
- **External open-source projects (15)** across Python, TypeScript, Rust and Go: CLI tools, web APIs, data pipelines and ML models.

### Metrics

1. **Claim accuracy (% grounded).** The share of numbers, badge values and versions in the README that match an exact key in `facts.json`. Target: 100%. Seeded drifts (e.g. 52 vs 44 tests) must be caught every time.
2. **Render validity.** 0 broken assets under GitHub's rules: no repo-relative `<video>` tags, no hero GIF over 5 MB, alt text on every image.
3. **The 5-second test.** Can a reviewer say what the project does within 5 seconds of seeing the top of the README?
4. **Rubric judge score (1–5).** An LLM judge, kept separate from the deterministic graders, scores clarity, problem framing, groundedness and absence of marketing fluff.
5. **Human edit distance.** How much a maintainer changes the generated README before accepting it.

### Ablations

| Configuration | Question it answers |
| :--- | :--- |
| Agent vs. deterministic `run` (no LLM) | How much does the LLM's rewrite of the story improve the 5-second test and judge score? |
| With vs. without the `final_check` edge | How often does the agent stop with a README that fails verify? |
| With vs. without the number guardrail in the tools | How often does the model try to write numbers that aren't in `facts.json`? |
| With vs. without the locked `facts.json` | Do the README, diagram and video storyboard drift apart without one shared source of numbers? |
