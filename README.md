<h1 align="center">Agentic-ReadMe-Creator</h1>

<p align="center">
  <em>Tired of opaque estimates and manual bottlenecks in a verified, media-rich readme pipeline grounded in real project runs?</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
  <a href="pyproject.toml"><img alt="python >=3.11" src="https://img.shields.io/badge/python->=3.11-3776AB?style=flat-square"></a>
  <a href="tests/"><img alt="tests 32 passed" src="https://img.shields.io/badge/tests-32%20passed-success?style=flat-square"></a>
</p>

<p align="center">
  <img alt="Terminal execution of Agentic-ReadMe-Creator: running verified pipeline, executing test verification, and outputting zero-drift documentation assets." src="assets/demo/hero-demo.svg" width="760">
</p>

<p align="center">
  <b>Agentic-ReadMe-Creator provides a verified, media-rich readme pipeline grounded in real project runs, grounding system execution and performance in deterministic data and verified automated test invariants.</b>
</p>

---

That run is real, and it is the whole pitch: **every claim, badge, and diagram node in this repository is mechanically checked against executable outputs** before PR creation.

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/architecture-dark.svg">
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/diagrams/architecture-static.svg">
    <img alt="Architecture of Agentic-ReadMe-Creator showing pipeline flow across verified components" src="assets/diagrams/architecture.svg" width="760">
  </picture>
</p>

<sub>Editable diagram source: <a href="assets/diagrams/architecture.excalidraw"><code>assets/diagrams/architecture.excalidraw</code></a></sub>

## Quickstart

```bash
git clone <repo-url> && cd Agentic-ReadMe-Creator
pip install -e .
pytest
python3 src/agentic_readme/cli.py
```

## Evidence & Ground Truth

> *Every figure above is verified against source code and execution logs in facts.json*

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
| Automated test suite with 32 passing tests verifying core system invariants. | `test_count: 32` | [`tests`](tests) | ✅ Verified |
| Modular architecture spanning 3709 lines of code across pipeline stages. | `loc: 3709` | [`src/`](src/) | ✅ Verified |
| Open source distribution under the MIT license. | `license: MIT` | [`LICENSE`](LICENSE) | ✅ Verified |

## Deliberately not included

- **No unverified claims: every figure is mechanically checked against executable outputs in facts.json**
- **No synthetic or staged mock runs: visual assets reflect genuine project execution**
- **No relative <video> tags in README that fail to render on GitHub**
- **No marketing buzzwords or generic template greetings**
