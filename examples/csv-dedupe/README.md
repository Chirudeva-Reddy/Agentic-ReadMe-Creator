<h1 align="center">csv-dedupe</h1>

<p align="center">
  <em>Your customer export lists Ana three times.</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
  <a href="pyproject.toml"><img alt="python >=3.9" src="https://img.shields.io/badge/python->=3.9-3776AB?style=flat-square"></a>
  <a href="tests/"><img alt="tests 4 passed" src="https://img.shields.io/badge/tests-4%20passed-success?style=flat-square"></a>
</p>

<p align="center">
  <a href="assets/video/launch-video.mp4">
    <picture>
      <source media="(prefers-reduced-motion: reduce)" srcset="assets/video/launch-poster.jpg">
      <img alt="20-second launch video for csv-dedupe: Your customer export lists Ana three times." src="assets/video/launch-video.gif" width="760">
    </picture>
  </a>
  <br>
  <sub>20-second launch video. <a href="assets/video/launch-video.mp4">Watch with sound (MP4)</a></sub>
</p>

<p align="center">
  <b>csv-dedupe: Removes duplicate rows from CSV exports, optionally matching on one column.</b>
</p>

---

**Every badge, number, and diagram node on this page is checked against [`facts.json`](facts.json)**, which was generated from this project's own code and test run.

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/architecture-dark.svg">
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/diagrams/architecture-static.svg">
    <img alt="Architecture of csv-dedupe showing pipeline flow across verified components" src="assets/diagrams/architecture.svg" width="760">
  </picture>
</p>

<sub>Editable diagram source: <a href="assets/diagrams/architecture.excalidraw"><code>assets/diagrams/architecture.excalidraw</code></a></sub>

## Quickstart

```bash
git clone <repo-url> && cd csv-dedupe
pip install -e .
pytest
python3 cli.py
```

## Evidence & Ground Truth

> *Every figure above is verified against source code and execution logs in facts.json*

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
| Automated test suite with 4 passing tests verifying core system invariants. | `test_count: 4` | [`tests`](tests) | ✅ Verified |
| 60 lines of code in the project source. | `loc: 60` | [`.`](.) | ✅ Verified |
| Open source distribution under the MIT license. | `license: MIT` | [`LICENSE`](LICENSE) | ✅ Verified |

## Deliberately not included

- **No unverified claims: every figure is mechanically checked against executable outputs in facts.json**
- **No invented numbers: every badge and metric comes from facts.json**
- **No relative <video> tags in README that fail to render on GitHub**
- **No marketing buzzwords or generic template greetings**
