---
name: agentic-readme
description: |
  Verified README generation and audit pipeline grounded in real project runs, plus a
  20-second launch video rendered with /brag. Use when creating, updating, auditing, or
  verifying README files, badges, architecture diagrams, or a launch video/GIF against facts.json.
---

# Agentic ReadMe Creator Skill

This skill provides an automated, compiler-like pipeline to ground, produce, and verify repository documentation against executable facts.

## When to use this skill

Activate this skill when:
1. Creating or rewriting a repository's `README.md`.
2. Auditing an existing README for fact drift (test counts, versions, lines of code, benchmark numbers).
3. Verifying badges, ensuring every badge links to verified evidence files in the codebase.
4. Detecting and eliminating leaked internal sprint/spec jargon (`Option C Architecture`, `Blueprint §11`, `localhost:8000`).
5. Generating media assets: Excalidraw architecture diagrams (light/dark SVGs), a VHS demo script, a `/brag` launch video storyboard, and (Phase 3) the launch video itself.
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

## Execution Workflow (Phases 0–3)

### Phase 0: Ground (Deterministic Fact Extraction)

Extract real repository metadata, run test suites, and produce locked narrative and factual contracts:

```bash
# Ground facts for target repository
agentic-readme ground <REPO_PATH> --audience "Developers, ML engineers" --hook "1-line pain hook"
```

**Artifacts Generated** (in `<REPO_PATH>/.agentic-readme/`):
- `facts.json`: Immutable ledger of every version, test count, line of code, and benchmark metric.
- `story.yaml`: Locked narrative contract (hook, problem, solution, key claims, architecture nodes, deliberate omissions).

> **Contract Gate**: Inspect `story.yaml` and `facts.json`. Never proceed to asset generation if facts or narrative are incorrect.
>
> **Rewrite `hook:` problem-first.** The default hook is just the project description. Replace it with one sentence naming the pain a stranger already recognises (e.g. "Your README says 40 tests pass. Your code has 3."), using only facts from the repo. It becomes the README tagline and the video's opening line.

### Phase 1: Produce (Parallel Asset Generation)

Generate candidate markdown and visual assets strictly from the locked contracts:

```bash
agentic-readme produce <REPO_PATH>
```

**Artifacts Generated**:
- `assets/diagrams/architecture.excalidraw`: Raw editable vector diagram.
- `assets/diagrams/architecture.svg` & `architecture-dark.svg`: Theme-aware SVGs embedded with `<picture>`.
- `assets/demo/hero-demo.svg`: an **illustrated** terminal preview (drawn, not recorded). The README labels it as such.
- `assets/demo/demo.tape`: a [VHS](https://github.com/charmbracelet/vhs) script. A real terminal GIF exists only if someone runs `vhs assets/demo/demo.tape`.
- `assets/video/brag_spec.json` + `scenes.md`: a problem-first **storyboard only** (hook → reveal → real run → proof → how to get it). No video is rendered in this phase.
- `README.md`: House-style candidate README. If `assets/video/launch-video.gif` exists, it is embedded as the hero (GIF linking to the MP4, poster for reduced motion); otherwise the illustrated SVG is used.

> `produce` overwrites `README.md`. Tell the user before running it on a repo with a hand-written README.

### Phase 2: Verify (Evaluator-Optimizer Loop)

Audit generated assets across Claim Auditor, Render Checker, and Voice Editor:

```bash
agentic-readme verify <REPO_PATH>
```

To run a standalone audit on an existing README:

```bash
agentic-readme audit <REPO_PATH>/README.md --facts <REPO_PATH>/.agentic-readme/facts.json
```

Or run Phases 0–2 end-to-end:

```bash
agentic-readme run <REPO_PATH>
```

### Phase 3: Launch video (agent step, needs /brag)

The CLI cannot render video. You, the agent, render it with `/brag-slim` from [latent-spaces/brag](https://github.com/latent-spaces/brag), then let `produce` embed it. Do this whenever the user wants a launch video, a demo GIF, or a README that explains the problem at a glance.

1. **Check prerequisites.** `node --version` (22+) and `ffmpeg -version`. Check whether a `brag-slim` or `brag` skill is available. If not, ask the user before installing it: `npx skills add https://github.com/latent-spaces/brag --skill brag-slim`. If the user declines or Node/ffmpeg are missing, skip to step 5 and tell them the README uses the illustrated SVG instead.
2. **Brief /brag-slim from the contracts, not from scratch.** Use `assets/video/brag_spec.json` as the storyboard (keep its scene order and `rules`), `story.yaml` for the hook and claims, and `facts.json` for every number. Run the commands shown in the "real run" scene yourself and copy their actual output into the video; never type up terminal output. If the command needs arguments (the storyboard includes its `--help` usage line), pass what a real user would, using sample data already in the repo. Show the product in use, not the architecture.
3. **Render and save exactly these files** (the names are what `produce` looks for):
   - `assets/video/launch-video.mp4`: 1920×1080, 30fps, ~20s, with the poster baked in as frame 0.
   - `assets/video/launch-poster.jpg`: the strongest settled frame.
   - `assets/video/launch-video.gif`: silent, under 5 MB. Keep the background static in GIF frames, then:
     ```bash
     ffmpeg -i frames/f%04d.png -vf "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" assets/video/launch-video.gif
     ```
   Keep /brag's plan and share copy next to them (`assets/video/brag-plan.md`, `share-copy.txt`). Don't commit `work/` intermediates.
4. **Embed and re-verify.** Run `agentic-readme produce <REPO_PATH>` (it now embeds the GIF as the hero), then `agentic-readme verify <REPO_PATH>`. Verify warns (it does not fail) if the GIF is over 5 MB or a linked file is missing. Treat any video-related warning as a blocker and fix it before finishing.
5. **Report honestly.** Tell the user whether a real video was rendered or the README fell back to the illustrated SVG, and where the MP4 and share copy are.

---

## Non-Negotiable House Style & Verification Rules

1. **Zero Fact Drift**: Every number, badge, and test count must match `facts.json` exactly. Never fabricate test counts or benchmark metrics.
2. **Evidence Links**: Every badge must wrap an anchor link pointing directly to an existing repository file (e.g. `tests/`, `LICENSE`, `pyproject.toml`).
3. **Badge Formatting**: Style must be `style=flat-square`. Maximum 6 badges in header.
4. **GitHub Rendering Constraints**: Never use `<video src="relative/path.mp4">` in Markdown (GitHub fails to render it). Use an image/GIF preview wrapped in an anchor link pointing to the video URL or release asset.
5. **Asset Ceilings**: Demo GIFs must remain strictly under 5 MB.
6. **No Leaked Internal Jargon**: Never leave development artifacts (`Option C Architecture`, `Blueprint §11/§13`, `localhost:8000`, `TODO`) in documentation.
7. **Clean Technical Voice**: Strip AI buzzwords (`revolutionary`, `seamless`, `delve`, `robust`, `elevate`), throat-clearing fillers (`In today's fast-paced world`), and template greetings (`Welcome to ...`).
