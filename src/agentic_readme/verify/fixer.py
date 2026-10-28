"""Fix the README problems that have one obviously right answer.

auto_fix(readme_path, facts, report) rewrites README.md in place:
  - test counts, lines of code, license and Python badges -> the values in facts.json
  - <video> tags GitHub won't play -> a clickable preview image linking to the video
  - noisy badge styles -> flat-square
  - filler phrases and leaked jargon -> deleted

Anything it can't fix stays in the next report, for a human or the agent to handle.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_readme.models import FactsLedger, FindingCategory, VerificationReport
from agentic_readme.rules import FORBIDDEN_BADGE_STYLES, PREFERRED_BADGE_STYLE
from agentic_readme.verify.voice import strip_slop


def auto_fix(readme_path: Path, facts: FactsLedger, report: VerificationReport) -> None:
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    drift = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT and f.actual]

    tests = facts.get_fact("test_count")
    if tests:
        expected = str(tests.value)
        text = re.sub(r"(?:tests?|pytest)-\d+(%20|\s+|-)?(?:passed)?", f"tests-{expected}%20passed", text, flags=re.IGNORECASE)
        for finding in drift:
            if finding.actual.isdigit():
                text = re.sub(rf"\b{finding.actual}\s+(?:passing\s+|unit\s+)?tests?\b", f"{expected} tests", text)

    loc = facts.get_fact("python_loc")
    if loc:
        expected = str(loc.value)
        text = re.sub(r"\bloc:\s*\d+\b", f"loc: {expected}", text)
        for finding in drift:
            if finding.actual.isdigit() and "lines of code" in finding.message:
                text = re.sub(rf"\b{finding.actual}\s+lines of code\b", f"{expected} lines of code", text)

    license_fact = facts.get_fact("license")
    if license_fact:
        text = re.sub(r"badge/licen[sc]e-[^-?\"'\s]+", f"badge/license-{license_fact.value}", text, flags=re.IGNORECASE)

    python = facts.get_fact("python_version")
    if python:
        expected = str(python.value).replace(" ", "%20")
        text = re.sub(r"badge/python-[0-9\.\+\>\<=\^%]+", f"badge/python-{expected}", text, flags=re.IGNORECASE)

    for finding in report.findings:
        actual = finding.actual or ""
        if finding.category == FindingCategory.RENDER_ISSUE and ("<video" in actual or "<source" in actual):
            text = re.sub(r'<video[^>]*>[\s\S]*?</video>|<video[^>]*/>', _video_to_preview, text, flags=re.IGNORECASE)

    for style in FORBIDDEN_BADGE_STYLES:
        text = text.replace(f"style={style}", f"style={PREFERRED_BADGE_STYLE}")

    text = strip_slop(text)

    for finding in report.findings:
        if finding.category == FindingCategory.JARGON_LEAKAGE and finding.actual:
            text = text.replace(finding.actual, "")

    readme_path.write_text(text, encoding="utf-8")


def _video_to_preview(match: re.Match) -> str:
    """Replace a <video> tag with its poster image, linked to the video file."""
    tag = match.group(0)
    src = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.IGNORECASE)
    poster = re.search(r'\bposter=["\']([^"\']+)["\']', tag, re.IGNORECASE)
    video = src.group(1) if src else "demo.mp4"
    image = poster.group(1) if poster else "assets/demo/hero-demo.svg"
    return (
        f'<p align="center">\n'
        f'  <a href="{video}">\n'
        f'    <img alt="Click to launch MP4 preview" src="{image}" width="760">\n'
        f'  </a><br>\n'
        f'  <sub><a href="{video}">▶ Download or view video directly ({video})</a></sub>\n'
        f'</p>'
    )
