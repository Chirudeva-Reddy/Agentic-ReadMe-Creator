---
name: agentic-readme
description: |
  Verified, media-rich README generation and audit pipeline grounded in real project runs.
  Use when creating, updating, auditing, or verifying README files, badges, architecture
  diagrams, or CLI demo recordings against facts.json ground truth.
---

# Agentic ReadMe Creator Skill

This skill provides an automated, compiler-like pipeline to ground, produce, and verify repository documentation against executable facts.

## When to use this skill

Activate this skill when:
1. Creating or rewriting a repository's `README.md`.
2. Auditing an existing README for fact drift (test counts, versions, lines of code, benchmark numbers).
3. Verifying badges, ensuring every badge links to verified evidence files in the codebase.
4. Detecting and eliminating leaked internal sprint/spec jargon (`Option C Architecture`, `Blueprint §11`, `localhost:8000`).
5. Generating media assets: Excalidraw architecture diagrams (light/dark SVGs), VHS demo scripts, and `/brag` launch video specs.
6. Enforcing house-style constraints and stripping hyperbolic AI writing and generic greetings.

---

## Prerequisites & Installation

Verify `agentic-readme` is installed in the active environment:

```bash
agentic-readme --help
```

If not installed, install in editable mode or via pip:

```bash
pip install -e .
```

---

## 3-Phase Execution Workflow

### Phase 0: Ground (Deterministic Fact Extraction)

Extract real repository metadata, run test suites, and produce locked narrative and factual contracts:

```bash
# Ground facts for target repository
agentic-readme ground <REPO_PATH> --audience "Developers, ML engineers" --hook "1-line pain hook"
```

**Artifacts Generated**:
- `facts.json`: Immutable ledger of every version, test count, line of code, and benchmark metric.
- `story.yaml`: Locked narrative contract (hook, problem, solution, key claims, architecture nodes, deliberate omissions).

> **Contract Gate**: Inspect `story.yaml` and `facts.json`. Never proceed to asset generation if facts or narrative are incorrect.

### Phase 1: Produce (Parallel Asset Generation)

Generate candidate markdown and visual assets strictly from the locked contracts:

```bash
agentic-readme produce <REPO_PATH>
```

**Artifacts Generated**:
- `assets/diagrams/architecture.excalidraw`: Raw editable vector diagram.
- `assets/diagrams/architecture.svg` & `architecture-dark.svg`: Theme-aware SVGs embedded with `<picture>`.
- `assets/demo/demo.tape` & `assets/demo/hero-demo.svg`: Terminal recording script and visual.
- `assets/video/brag_spec.json`: Launch video storyboard and scene breakdown.
- `README.md`: House-style candidate README.

### Phase 2: Verify (Evaluator-Optimizer Loop)

Audit generated assets across Claim Auditor, Render Checker, and Voice Editor:

```bash
agentic-readme verify <REPO_PATH>
```

To run a standalone audit on an existing README:

```bash
agentic-readme audit <REPO_PATH>/README.md --facts <REPO_PATH>/facts.json
```

Or run all 3 phases end-to-end:

```bash
agentic-readme run <REPO_PATH>
```

---

## Non-Negotiable House Style & Verification Rules

1. **Zero Fact Drift**: Every number, badge, and test count must match `facts.json` exactly. Never fabricate test counts or benchmark metrics.
2. **Evidence Links**: Every badge must wrap an anchor link pointing directly to an existing repository file (e.g. `tests/`, `LICENSE`, `pyproject.toml`).
3. **Badge Formatting**: Style must be `style=flat-square`. Maximum 6 badges in header.
4. **GitHub Rendering Constraints**: Never use `<video src="relative/path.mp4">` in Markdown (GitHub fails to render it). Use an image/GIF preview wrapped in an anchor link pointing to the video URL or release asset.
5. **Asset Ceilings**: Demo GIFs must remain strictly under 5 MB.
6. **No Leaked Internal Jargon**: Never leave development artifacts (`Option C Architecture`, `Blueprint §11/§13`, `localhost:8000`, `TODO`) in documentation.
7. **Clean Technical Voice**: Strip AI buzzwords (`revolutionary`, `seamless`, `delve`, `robust`, `elevate`), throat-clearing fillers (`In today's fast-paced world`), and template greetings (`Welcome to ...`).
