"""Check the README's wording and layout against the house style.

check_voice(readme_path) flags marketing buzzwords, filler openers, template greetings,
banned phrases, too many badges, noisy badge styles, and missing sections.
strip_slop(text) deletes the worst offenders; verify's auto-fixer uses it.

All word lists live in rules.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_readme.models import FindingCategory, FindingSeverity, VerificationReport
from agentic_readme.rules import (
    AI_BUZZWORDS,
    AI_THROAT_CLEARING,
    FORBIDDEN_BADGE_STYLES,
    FORBIDDEN_PHRASES,
    MAX_BADGE_COUNT,
    REQUIRED_SECTIONS,
    SLOP_TO_STRIP,
    TEMPLATE_SLOP,
)

SLOP = FindingCategory.VOICE_SLOP

# One rule per phrase list:
# (phrases, match whole words only?, message, what good looks like, how to fix it)
# The messages use {phrase} and {count}.
PHRASE_RULES = [
    (AI_BUZZWORDS, True,
     "AI marketing buzzword / inflated tone detected: '{phrase}' (found {count}x).",
     "Plain, concrete technical prose", "Replace '{phrase}' with objective engineering descriptions."),
    (AI_THROAT_CLEARING, True,
     "Formulaic AI transition / throat-clearing detected: '{phrase}'.",
     "Direct statement of fact without filler", "Cut '{phrase}' and begin directly with the subject."),
    (TEMPLATE_SLOP, True,
     "Generic template cliche detected: '{phrase}'.",
     "House style hook naming specific user pain", "Remove '{phrase}' and focus on the real utility and verified run."),
    (FORBIDDEN_PHRASES, False,
     "Forbidden house style phrase detected: '{phrase}'.",
     "Clean technical prose without template filler or marketing pleas", "Remove '{phrase}' to maintain house style tone."),
]


def check_voice(readme_path: Path, report: VerificationReport | None = None) -> VerificationReport:
    if report is None:
        report = VerificationReport()
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    name = readme_path.name

    for phrases, whole_words, message, expected, fix in PHRASE_RULES:
        for phrase in phrases:
            pattern = re.escape(phrase)
            if whole_words:
                pattern = rf"\b{pattern}\b"
            count = len(re.findall(pattern, text, re.IGNORECASE))
            if count:
                report.add_finding(
                    SLOP, FindingSeverity.WARNING, message.format(phrase=phrase, count=count),
                    location=name, expected=expected, actual=phrase, suggested_fix=fix.format(phrase=phrase),
                )

    badge_count = len(re.findall(r"img\.shields\.io/badge", text))
    if badge_count > MAX_BADGE_COUNT:
        report.add_finding(
            SLOP, FindingSeverity.MINOR,
            f"Excessive badges ({badge_count} badges, max recommended {MAX_BADGE_COUNT}). Visual noise degrades readability.",
            location=name, expected=f"<= {MAX_BADGE_COUNT} high-signal badges linking to evidence",
            actual=f"{badge_count} badges",
            suggested_fix="Prune vanity badges and keep only badges linked to verifiable evidence.",
        )

    for style in FORBIDDEN_BADGE_STYLES:
        if f"style={style}" in text:
            report.add_finding(
                SLOP, FindingSeverity.MINOR,
                f"Forbidden badge style '{style}' detected (visual noise). House style mandates 'flat-square'.",
                location=name, expected="style=flat-square", actual=f"style={style}",
                suggested_fix="Replace 'style=for-the-badge' with 'style=flat-square'.",
            )

    for pattern, description in REQUIRED_SECTIONS:
        if not re.search(pattern, text, re.IGNORECASE):
            report.add_finding(
                SLOP, FindingSeverity.MINOR, f"Missing recommended house style element: {description}.",
                location=name, expected=description, actual="Missing section",
                suggested_fix=f"Add '{description}' following the duet/body2health house style rubric.",
            )

    return report


def strip_slop(text: str) -> str:
    """Delete filler openers, template greetings and banned phrases."""
    for phrase in AI_THROAT_CLEARING:
        text = re.sub(rf"\b{re.escape(phrase)}\b,?\s*", "", text, flags=re.IGNORECASE)
    for phrase in SLOP_TO_STRIP + FORBIDDEN_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text
