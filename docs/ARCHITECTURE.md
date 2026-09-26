# Architecture Specification

## Overview

**Agentic ReadMe Creator** is a verified, media-rich documentation pipeline grounded in real runs of your project. Rather than treating documentation as unconstrained LLM generation, it treats documentation as a verified compiler problem:

1. **Ground** every claim and metric in verifiable outputs.
2. **Lock** an immutable contract (`story.yaml` + `facts.json`, kept in `.agentic-readme/`) before parallel fan-out.
3. **Produce** all media assets (diagrams, demos, launch video configs, README) from that single source of truth.
4. **Audit** cross-asset consistency with an evaluator-optimizer loop to eliminate fact drift, leaked internal jargon, and GitHub rendering bugs before human review.

---

## The 3-Phase Architecture

```mermaid
flowchart TD
    subgraph Phase0[Phase 0: GROUND - Single Agent Sequential]
        A[Repository Codebase] --> B[Repo Analyst]
        B --> C[Sandboxed Execution & Static Analysis]
        C --> D[story.yaml: Story Spec]
        C --> E[facts.json: Facts Ledger]
    end

    D & E --> GATE{⏸ Human Gate}

    subgraph Phase1[Phase 1: PRODUCE - Parallel Fan-Out]
        GATE -->|Read-Only| F1[Diagram Agent]
        GATE -->|Read-Only| F2[Demo Agent]
        GATE -->|Read-Only| F3[Video Agent]
        GATE -->|Read-Only| F4[Writer Agent]

        F1 --> G1[.excalidraw + Light/Dark SVGs]
        F2 --> G2[VHS Tape Script + Illustrated Hero SVG]
        F3 --> G3[/brag 20s Spec + Scene Table]
        F4 --> G4[Candidate README.md]
    end

    subgraph Phase2[Phase 2: VERIFY - Evaluator-Optimizer Loop]
        G1 & G2 & G3 & G4 --> H[Evaluator-Optimizer]
        H --> I1[Claim Auditor]
        H --> I2[Render Checker]
        H --> I3[Voice Editor]

        I1 -.->|Discrepancy / Drift| H
        I2 -.->|GitHub Render Issue| H
        I3 -.->|AI Slop / Hype| H
    end

    H -->|Verified Artifacts| PR[Verified PR Bundle]
```

### Phase 0: Ground (Single Agent, Sequential)
- **Role**: `RepoAnalyst`
- **Inputs**: Target repository directory.
- **Actions**:
  - Scans package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`).
  - Executes unit tests, benchmark scripts, or `--help` outputs in a safe sandbox.
  - Deterministically extracts:
    - Test counts and passing assertions.
    - Supported language and platform versions.
    - Lines of code and project file metrics.
    - Benchmark latencies, throughputs, and prices.
- **Outputs**:
  - `story.yaml` (`StorySpec`): The narrative contract (pain-first hook, problem, solution, 3 verified key claims, architecture nodes, quickstart commands, deliberate omissions).
  - `facts.json` (`FactsLedger`): Immutable dictionary where every number, version, and name is recorded with its source file and timestamp.

### ⏸ Human Gate
The human operator reviews and edits `story.yaml` and `facts.json`. No asset generation is permitted until the narrative and facts are locked.

### Phase 1: Produce (Parallel Fan-Out)
All producers receive `story.yaml` and `facts.json` in **read-only** mode. Agents are forbidden from inventing ungrounded claims.
- **Diagram Agent**:
  - Maps code-grounded `architecture_nodes` to `.excalidraw` geometry.
  - Outputs `assets/diagrams/architecture.excalidraw`, `architecture.svg`, and `architecture-dark.svg` (for `prefers-color-scheme: dark`).
- **Demo Agent**:
  - Generates VHS tape scripts (`assets/demo/demo.tape`) with realistic typing pauses and verified quickstart commands.
  - Enforces the hard 5MB ceiling for hero GIFs.
- **Video Agent**:
  - Prepares a problem-first 20s `/brag` storyboard (`assets/video/brag_spec.json`) and scene/time table. It does **not** render video: an AI agent renders it with `/brag-slim` (skill Phase 3), and the Writer Agent embeds `assets/video/launch-video.gif` as the hero once it exists.
  - Enforces GitHub-compatible embed pattern (GIF preview linking to external MP4).
- **Writer Agent**:
  - Generates `README.md` following the proven house style rubric (`duet` / `body2health`).

### Phase 2: Verify (Evaluator-Optimizer Loop)
Runs up to 2 verification passes:
- **Claim Auditor**:
  - Catches fact drift between badges, text, and `facts.json` (e.g. badge claiming 52 passed while text claims 44).
  - Flags leaked internal jargon ("Option C Architecture", "Blueprint §11/§13", "PRD §4").
- **Render Checker**:
  - Rejects `<video src="...">` tags with relative repo paths (which break silently on GitHub).
  - Enforces file size limits (Hero GIF ≤ 5MB, attachments ≤ 10MB).
  - Ensures descriptive alt text on all visual elements.
  - Validates local file link integrity.
- **Voice Editor**:
  - Applies Humanizer patterns (25 signs of AI writing from Wikipedia).
  - Eliminates inflated marketing adjectives ("revolutionary", "agonizing uncertainty", "seamlessly").
  - Strips generic template greetings ("Welcome to ... 👋").
- **PR Output**: Verified markdown and media assets bundled ready for pull request review.
