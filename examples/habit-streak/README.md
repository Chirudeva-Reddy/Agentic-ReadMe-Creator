<h1 align="center">habit-streak</h1>

<p align="center">
  <em>Track daily habits and see your longest streak.</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
  <a href="package.json"><img alt="version 1.0.0" src="https://img.shields.io/badge/version-1.0.0-CB3837?style=flat-square"></a>
  <a href="./"><img alt="tests 2 passed" src="https://img.shields.io/badge/tests-2%20passed-success?style=flat-square"></a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/demo/hero-demo-static.svg">
    <img alt="Illustrated terminal preview of the habit-streak quickstart commands." src="assets/demo/hero-demo.svg" width="760">
  </picture>
  <br>
  <sub>Illustrated preview of the quickstart, not a screen recording. Record the real run with <code>vhs assets/demo/demo.tape</code>.</sub>
</p>

<p align="center">
  <b>habit-streak: Track daily habits and see your longest streak.</b>
</p>

---

**Every badge, number, and diagram node on this page is checked against [`facts.json`](.agentic-readme/facts.json)**, which was generated from this project's own code and test run.

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/architecture-dark.svg">
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/diagrams/architecture-static.svg">
    <img alt="Architecture of habit-streak showing pipeline flow across verified components" src="assets/diagrams/architecture.svg" width="760">
  </picture>
</p>

<sub>Editable diagram source: <a href="assets/diagrams/architecture.excalidraw"><code>assets/diagrams/architecture.excalidraw</code></a></sub>

## Quickstart

```bash
git clone <repo-url> && cd habit-streak
npm install
npm test
npm start
```

## Evidence & Ground Truth

> *Every figure above is verified against source code and execution logs in facts.json*

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
| Automated test suite with 2 passing tests verifying core system invariants. | `test_count: 2` | [`.`](.) | ✅ Verified |
| Open source distribution under the MIT license. | `license: MIT` | [`LICENSE`](LICENSE) | ✅ Verified |

## Deliberately not included

- **No unverified claims: every figure is mechanically checked against executable outputs in facts.json**
- **No invented numbers: every badge and metric comes from facts.json**
- **No relative <video> tags in README that fail to render on GitHub**
- **No marketing buzzwords or generic template greetings**
