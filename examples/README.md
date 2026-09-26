# Examples

Two small projects, each run through the full pipeline. Everything in these folders except the project's own code was written by `agentic-readme run`, and nothing was edited by hand afterwards.

| Example | Stack | What the project does | Generated README |
| :--- | :--- | :--- | :--- |
| [`tip-splitter/`](tip-splitter/) | Python + pytest | CLI that splits a restaurant bill, tip included | [README.md](tip-splitter/README.md) |
| [`habit-streak/`](habit-streak/) | Node + `node --test` | Finds the longest run of consecutive days in a list of dates | [README.md](habit-streak/README.md) |
| [`csv-dedupe/`](csv-dedupe/) | Python + pytest, **with launch video** | Removes duplicate rows from CSV exports | [README.md](csv-dedupe/README.md) |

`csv-dedupe` also went through Phase 3: the hook was rewritten problem-first, and the launch video was rendered with /brag and embedded by `produce`. The [case study](https://chirudeva-reddy.github.io/Agentic-ReadMe-Creator/#case-study) walks through every step with real output.

## What the pipeline added to each folder

```text
tip-splitter/
├── cli.py, tests/, pyproject.toml, LICENSE   ← the original project (input)
├── .agentic-readme/
│   ├── facts.json      ← Phase 0: every number found in the code, with the file it came from
│   └── story.yaml      ← Phase 0: the pitch, claims, and quickstart (edit this to change the README)
├── README.md           ← Phase 1: the generated README
└── assets/
    ├── diagrams/       ← Phase 1: Excalidraw source + light, dark, and static SVGs
    ├── demo/           ← Phase 1: VHS tape script + hero terminal SVG
    └── video/          ← Phase 1: 20-second /brag storyboard (brag_spec.json, scenes.md)
```

Phase 2 (verify) doesn't write files. It checks that the README, the diagram, and the video storyboard agree with `facts.json`.

## Run them yourself

From the repository root, after [installing](../docs/INSTALL.md):

```bash
agentic-readme run examples/tip-splitter
```

```bash
agentic-readme run examples/habit-streak
```

Each run finishes with `0 fatal errors, 0 warnings`.

`csv-dedupe` has a hand-edited hook. Re-running `ground` (or `run`) keeps it: when `story.yaml` already exists, only its numbers are refreshed from the new `facts.json`.

```bash
agentic-readme run examples/csv-dedupe
```

## Watch it catch a lie

The point of the tool is that a README can't claim something the code doesn't back up. Try it:

1. Open `examples/tip-splitter/README.md` and change `tests-3%20passed` to `tests-40%20passed`, and `license-MIT-blue` to `license-Apache-blue`.
2. Audit it:

   ```bash
   agentic-readme audit examples/tip-splitter/README.md --facts examples/tip-splitter/.agentic-readme/facts.json
   ```

3. You get this, and the command exits with code 1 (so CI fails too):

   ```text
   fact_drift │ Fatal Functional Bug │ Test count badge drift: badge claims 40 tests passed, but facts ledger records 3.
   fact_drift │ Fatal Functional Bug │ License badge discrepancy: badge states Apache, actual LICENSE file is MIT.
   Summary: 23 facts checked. 2 fatal errors, 0 warnings.
   ```

4. Undo your change with `git checkout examples/tip-splitter/README.md`.

## Use it on your own project

```bash
cd path/to/your-project
agentic-readme ground . --hook "One sentence a stranger would understand."
# read story.yaml and facts.json and fix anything that's wrong
agentic-readme produce .
agentic-readme verify .
```

`run` does all three steps in one go. Splitting them lets you review `story.yaml` before any README text is written.
