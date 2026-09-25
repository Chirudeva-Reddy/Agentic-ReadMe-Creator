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
    raw = "In today's fast-paced world, Welcome to our engine. ⭐ Star us on GitHub!"
    cleaned = editor.sanitize(raw)
    assert "In today's fast-paced world" not in cleaned
    assert "Welcome to" not in cleaned
    assert "Star us on GitHub" not in cleaned


def test_voice_editor_catches_forbidden_phrases(tmp_path: Path):
    """Flags house style forbidden phrases like 'Feel free to contribute', '⭐ Star us on GitHub'."""
    readme = tmp_path / "README.md"
    readme.write_text("""# Project
Feel free to contribute! ⭐ Star us on GitHub! Maintained? yes.
""", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    forbidden_findings = [f for f in report.findings if "Forbidden house style phrase" in f.message]
    assert len(forbidden_findings) >= 3
    phrases_flagged = [f.actual for f in forbidden_findings]
    assert any("Feel free to contribute" in p for p in phrases_flagged)
    assert any("Star us on GitHub" in p for p in phrases_flagged)
    assert any("Maintained? yes" in p for p in phrases_flagged)


def test_voice_editor_catches_forbidden_badge_styles(tmp_path: Path):
    """Flags for-the-badge visual noise from NLP-Proj."""
    readme = tmp_path / "README.md"
    readme.write_text("""# Project
[![Tests](https://img.shields.io/badge/tests-52-blue?style=for-the-badge)](tests/)
""", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    style_findings = [f for f in report.findings if "Forbidden badge style" in f.message]
    assert len(style_findings) == 1
    assert "for-the-badge" in style_findings[0].actual


def test_voice_editor_catches_missing_house_style_sections(tmp_path: Path):
    """Flags missing house style structural sections."""
    readme = tmp_path / "README.md"
    readme.write_text("# Minimal Repo\nJust some code.\n", encoding="utf-8")

    editor = VoiceEditor()
    report = editor.check(readme)

    section_findings = [f for f in report.findings if "Missing recommended house style element" in f.message]
    assert len(section_findings) >= 3

