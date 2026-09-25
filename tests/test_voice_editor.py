"""Tests for Phase 2 Voice Editor: AI slop, marketing tone, and badge noise."""

from pathlib import Path
from agentic_readme.core.models import FindingCategory, FindingSeverity, VerificationReport
from agentic_readme.verify.voice_editor import VoiceEditor


def test_voice_editor_catches_ai_buzzwords_and_hype(tmp_path: Path):
    """Flags inflated emotional or AI marketing adjectives (e.g. ClaimLens' 'agonizing uncertainty')."""
    readme = tmp_path / "README.md"
    readme.write_text("""# Showcase
Drivers are left stranded in agonizing uncertainty for weeks.
Our revolutionary tool allows users to delve seamlessly into the architecture.
""", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    slop_findings = [f for f in report.findings if f.category == FindingCategory.VOICE_SLOP]
    assert len(slop_findings) >= 4

    words_found = [f.actual.lower() for f in slop_findings]
    assert "agonizing uncertainty" in words_found
    assert "revolutionary" in words_found
    assert "delve" in words_found
    assert "seamlessly" in words_found


def test_voice_editor_catches_template_slop(tmp_path: Path):
    """Flags template clichés from odoo-salon-erp."""
    readme = tmp_path / "README.md"
    readme.write_text("""# Project
Welcome to our project!
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com)
""", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    slop_findings = [f for f in report.findings if f.category == FindingCategory.VOICE_SLOP]
    assert any("Welcome to" in f.actual for f in slop_findings)


def test_voice_editor_catches_badge_noise(tmp_path: Path):
    """Flags 9+ noisy badges (anti-pattern from NLP-Proj)."""
    readme = tmp_path / "README.md"
    badges = "\n".join([f"[![B{i}](https://img.shields.io/badge/b{i}-val-blue.svg)](link)" for i in range(9)])
    readme.write_text(f"# Project\n{badges}\n", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    badge_findings = [f for f in report.findings if "Excessive badges" in f.message]
    assert len(badge_findings) == 1
    assert "9 badges" in badge_findings[0].actual


def test_voice_editor_sanitize():
    editor = VoiceEditor()
    raw = "In today's fast-paced world, Welcome to our engine."
    cleaned = editor.sanitize(raw)
    assert "In today's fast-paced world" not in cleaned
    assert "Welcome to" not in cleaned
