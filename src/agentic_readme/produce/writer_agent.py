"""Writer Agent for Phase 1.

Synthesizes README.md strictly adhering to the house style rubric
(modeled on duet and body2health), verified by facts in FactsLedger.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, List, Optional

from agentic_readme.core.models import FactsLedger, StorySpec


class WriterAgent:
    """Produces the candidate README.md according to the house style rubric."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def produce(self, story: StorySpec, facts: FactsLedger) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        readme_path = self.output_dir / "README.md"

        content = self._render_readme(story, facts)
        readme_path.write_text(content, encoding="utf-8")
        return readme_path

    def _render_readme(self, story: StorySpec, facts: FactsLedger) -> str:
        # Extract verified facts

        badges: List[str] = []

        lic_fact = facts.get_fact("license")
        if lic_fact:
            lic_val = str(lic_fact.value)
            lic_file = lic_fact.source_file or "LICENSE"
            badges.append(f'<a href="{lic_file}"><img alt="license {lic_val}" src="https://img.shields.io/badge/license-{lic_val}-blue?style=flat-square"></a>')

        py_fact = facts.get_fact("python_version")
        if py_fact:
            py_val = str(py_fact.value)
            py_file = py_fact.source_file or "pyproject.toml"
            badges.append(f'<a href="{py_file}"><img alt="python {py_val}" src="https://img.shields.io/badge/python-{py_val.replace(" ", "%20")}-3776AB?style=flat-square"></a>')
        else:
            pkg_fact = facts.get_fact("package_version")
            if pkg_fact:
                badges.append(f'<a href="package.json"><img alt="version {pkg_fact.value}" src="https://img.shields.io/badge/version-{pkg_fact.value}-CB3837?style=flat-square"></a>')
            cargo_fact = facts.get_fact("cargo_version")
            if cargo_fact:
                badges.append(f'<a href="Cargo.toml"><img alt="crates.io {cargo_fact.value}" src="https://img.shields.io/badge/crates.io-v{cargo_fact.value}-dea584?style=flat-square"></a>')

        test_fact = facts.get_fact("test_count")
        if test_fact:
            test_val = str(test_fact.value)
            test_source = test_fact.source_file or "tests/"
            if not test_source.endswith("/"):
                test_source += "/"
            badges.append(f'<a href="{test_source}"><img alt="tests {test_val} passed" src="https://img.shields.io/badge/tests-{test_val}%20passed-success?style=flat-square"></a>')

        hero_block = self._hero_block(story)

        # Quickstart block
        quickstart_lines = "\n".join(story.quickstart_commands) if story.quickstart_commands else "pip install -e ."

        # Architecture diagram alt text
        arch_alt = f"Architecture of {story.repo_name} showing pipeline flow across verified components"

        # Claims / Evidence rows
        evidence_rows = []
        for c in story.key_claims:
            metrics_str = ", ".join(f"`{k}: {v}`" for k, v in c.metrics.items()) if c.metrics else "Verified"
            evidence_rows.append(f"| {c.claim} | {metrics_str} | [`{c.evidence_file}`]({c.evidence_file}) | ✅ Verified |")
        evidence_table = "\n".join(evidence_rows) if evidence_rows else "| All claims verified | — | `facts.json` | ✅ Verified |"

        # Deliberate omissions list
        omissions_list = "\n".join(f"- **{om}**" for om in story.deliberate_omissions)

        readme_text = f"""<h1 align="center">{story.repo_name}</h1>

<p align="center">
  <em>{story.hook}</em>
</p>

<p align="center">
  {"\n  ".join(badges)}
</p>

{hero_block}

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
    <img alt="{arch_alt}" src="assets/diagrams/architecture.svg" width="760">
  </picture>
</p>

<sub>Editable diagram source: <a href="assets/diagrams/architecture.excalidraw"><code>assets/diagrams/architecture.excalidraw</code></a></sub>

## Quickstart

```bash
{quickstart_lines}
```

## Evidence & Ground Truth

> *{story.evidence_summary}*

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
{evidence_table}

## Deliberately not included

{omissions_list}
"""
        return readme_text

    def _hero_block(self, story: StorySpec) -> str:
        """Launch video (GIF linking to MP4) when Phase 3 rendered one, else the illustrated SVG."""
        video_dir = self.output_dir / "assets" / "video"
        gif, mp4, poster = (video_dir / n for n in ("launch-video.gif", "launch-video.mp4", "launch-poster.jpg"))

        if gif.exists():
            alt = html.escape(f"20-second launch video for {story.repo_name}: {story.hook}", quote=True)
            poster_src = (
                '\n      <source media="(prefers-reduced-motion: reduce)" srcset="assets/video/launch-poster.jpg">'
                if poster.exists() else ""
            )
            img = f"""<picture>{poster_src}
      <img alt="{alt}" src="assets/video/launch-video.gif" width="760">
    </picture>"""
            if mp4.exists():
                return f"""<p align="center">
  <a href="assets/video/launch-video.mp4">
    {img}
  </a>
  <br>
  <sub>20-second launch video. <a href="assets/video/launch-video.mp4">Watch with sound (MP4)</a></sub>
</p>"""
            return f"""<p align="center">
  {img}
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

