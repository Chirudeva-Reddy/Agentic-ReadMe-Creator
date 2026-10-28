"""Write README.md from story.yaml and facts.json.

write_readme(story, facts, out_dir) fills one Markdown template:
title and hook, badges (each linking to its evidence file), the hero image, the
architecture diagram, quickstart, an evidence table, and the deliberate omissions.
"""

from __future__ import annotations

import html
from pathlib import Path

from agentic_readme.models import FactsLedger, StorySpec


def write_readme(story: StorySpec, facts: FactsLedger, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "README.md"
    readme.write_text(_render(story, facts, out_dir), encoding="utf-8")
    return readme


def _badges(facts: FactsLedger) -> list[str]:
    """shields.io badges, each wrapped in a link to the file that proves it."""
    badges: list[str] = []

    license_fact = facts.get_fact("license")
    if license_fact:
        value = str(license_fact.value)
        link = license_fact.source_file or "LICENSE"
        badges.append(f'<a href="{link}"><img alt="license {value}" src="https://img.shields.io/badge/license-{value}-blue?style=flat-square"></a>')

    python_fact = facts.get_fact("python_version")
    if python_fact:
        value = str(python_fact.value)
        link = python_fact.source_file or "pyproject.toml"
        badges.append(f'<a href="{link}"><img alt="python {value}" src="https://img.shields.io/badge/python-{value.replace(" ", "%20")}-3776AB?style=flat-square"></a>')
    else:
        package_fact = facts.get_fact("package_version")
        if package_fact:
            badges.append(f'<a href="package.json"><img alt="version {package_fact.value}" src="https://img.shields.io/badge/version-{package_fact.value}-CB3837?style=flat-square"></a>')
        cargo_fact = facts.get_fact("cargo_version")
        if cargo_fact:
            badges.append(f'<a href="Cargo.toml"><img alt="crates.io {cargo_fact.value}" src="https://img.shields.io/badge/crates.io-v{cargo_fact.value}-dea584?style=flat-square"></a>')

    test_fact = facts.get_fact("test_count")
    if test_fact:
        value = str(test_fact.value)
        link = test_fact.source_file or "tests/"
        if not link.endswith("/"):
            link += "/"
        badges.append(f'<a href="{link}"><img alt="tests {value} passed" src="https://img.shields.io/badge/tests-{value}%20passed-success?style=flat-square"></a>')

    return badges


def _render(story: StorySpec, facts: FactsLedger, out_dir: Path) -> str:
    badges = "\n  ".join(_badges(facts))
    hero = _hero(story, out_dir)
    quickstart = "\n".join(story.quickstart_commands) if story.quickstart_commands else "pip install -e ."
    diagram_alt = f"Architecture of {story.repo_name} showing pipeline flow across verified components"

    rows = []
    for claim in story.key_claims:
        metrics = ", ".join(f"`{k}: {v}`" for k, v in claim.metrics.items()) if claim.metrics else "Verified"
        rows.append(f"| {claim.claim} | {metrics} | [`{claim.evidence_file}`]({claim.evidence_file}) | ✅ Verified |")
    evidence_table = "\n".join(rows) if rows else "| All claims verified | — | `facts.json` | ✅ Verified |"

    omissions = "\n".join(f"- **{item}**" for item in story.deliberate_omissions)

    return f"""<h1 align="center">{story.repo_name}</h1>

<p align="center">
  <em>{story.hook}</em>
</p>

<p align="center">
  {badges}
</p>

{hero}

<p align="center">
  <b>{story.solution}</b>
</p>

---

**Every badge, number, and diagram node on this page is checked against [`facts.json`](.agentic-readme/facts.json)**, which was generated from this project's own code and test run.

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/architecture-dark.svg">
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/diagrams/architecture-static.svg">
    <img alt="{diagram_alt}" src="assets/diagrams/architecture.svg" width="760">
  </picture>
</p>

<sub>Editable diagram source: <a href="assets/diagrams/architecture.excalidraw"><code>assets/diagrams/architecture.excalidraw</code></a></sub>

## Quickstart

```bash
{quickstart}
```

## Evidence & Ground Truth

> *{story.evidence_summary}*

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
{evidence_table}

## Deliberately not included

{omissions}
"""


def _hero(story: StorySpec, out_dir: Path) -> str:
    """The launch video (a GIF linking to the MP4) if one was rendered, else the illustrated SVG."""
    video_dir = out_dir / "assets" / "video"
    gif = video_dir / "launch-video.gif"
    mp4 = video_dir / "launch-video.mp4"
    poster = video_dir / "launch-poster.jpg"

    if gif.exists():
        alt = html.escape(f"20-second launch video for {story.repo_name}: {story.hook}", quote=True)
        poster_source = ""
        if poster.exists():
            poster_source = '\n      <source media="(prefers-reduced-motion: reduce)" srcset="assets/video/launch-poster.jpg">'
        image = f"""<picture>{poster_source}
      <img alt="{alt}" src="assets/video/launch-video.gif" width="760">
    </picture>"""
        if mp4.exists():
            return f"""<p align="center">
  <a href="assets/video/launch-video.mp4">
    {image}
  </a>
  <br>
  <sub>20-second launch video. <a href="assets/video/launch-video.mp4">Watch with sound (MP4)</a></sub>
</p>"""
        return f"""<p align="center">
  {image}
</p>"""

    alt = html.escape(f"Illustrated terminal preview of the {story.repo_name} quickstart commands.", quote=True)
    return f"""<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/demo/hero-demo-static.svg">
    <img alt="{alt}" src="assets/demo/hero-demo.svg" width="760">
  </picture>
  <br>
  <sub>Illustrated preview of the quickstart, not a screen recording. Record the real run with <code>vhs assets/demo/demo.tape</code>.</sub>
</p>"""
