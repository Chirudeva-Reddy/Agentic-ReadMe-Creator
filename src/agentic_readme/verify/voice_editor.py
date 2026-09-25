"""Voice Editor for Phase 2 Verification.

Applies Humanizer patterns (derived from Wikipedia's Signs of AI writing)
and house style guidelines to eliminate generic AI fluff, inflated marketing
tone, and template slop.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from agentic_readme.core.models import (
    FindingCategory,
    FindingSeverity,
    VerificationReport,
)
from agentic_readme.rubrics.house_style import (
    FORBIDDEN_BADGE_STYLES,
    FORBIDDEN_PHRASES,
    MAX_BADGE_COUNT,
    REQUIRED_SECTIONS,
)
from agentic_readme.rubrics.humanizer_rules import (
    AI_BUZZWORDS,
    AI_THROAT_CLEARING,
    TEMPLATE_SLOP,
)


class VoiceEditor:
    """Audits and refines the tone and voice of the generated README."""

    def check(
        self,
        readme_path: Path,
        report: Optional[VerificationReport] = None,
    ) -> VerificationReport:
        rep = report or VerificationReport()
        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")

        self._check_buzzwords(readme_text, readme_path, rep)
        self._check_throat_clearing(readme_text, readme_path, rep)
        self._check_template_slop(readme_text, readme_path, rep)
        self._check_forbidden_phrases(readme_text, readme_path, rep)
        self._check_badge_noise(readme_text, readme_path, rep)
        self._check_badge_styles(readme_text, readme_path, rep)
        self._check_house_style_sections(readme_text, readme_path, rep)

        return rep


    def _check_buzzwords(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag inflated adjectives and AI marketing buzzwords."""
        for word in AI_BUZZWORDS:
            # Case-insensitive whole word search
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            matches = list(pattern.finditer(text))
            if matches:
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.WARNING,
                    message=f"AI marketing buzzword / inflated tone detected: '{word}' (found {len(matches)}x).",
                    location=f"{readme_path.name}",
                    expected="Plain, concrete technical prose",
                    actual=word,
                    suggested_fix=f"Replace '{word}' with objective engineering descriptions.",
                )

    def _check_throat_clearing(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag stereotypical AI introductory copulas and filler phrases."""
        for phrase in AI_THROAT_CLEARING:
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            if pattern.search(text):
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.WARNING,
                    message=f"Formulaic AI transition / throat-clearing detected: '{phrase}'.",
                    location=f"{readme_path.name}",
                    expected="Direct statement of fact without filler",
                    actual=phrase,
                    suggested_fix=f"Cut '{phrase}' and begin directly with the subject.",
                )

    def _check_template_slop(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag generic README template cliches ('Welcome to ...', etc.)."""
        for slop in TEMPLATE_SLOP:
            pattern = re.compile(rf"\b{re.escape(slop)}\b", re.IGNORECASE)
            if pattern.search(text):
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.WARNING,
                    message=f"Generic template cliche detected: '{slop}'.",
                    location=f"{readme_path.name}",
                    expected="House style hook naming specific user pain",
                    actual=slop,
                    suggested_fix=f"Remove '{slop}' and focus on the real utility and verified run.",
                )

    def _check_forbidden_phrases(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag phrases explicitly prohibited by house style rubric."""
        for phrase in FORBIDDEN_PHRASES:
            pattern = re.compile(rf"{re.escape(phrase)}", re.IGNORECASE)
            if pattern.search(text):
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.WARNING,
                    message=f"Forbidden house style phrase detected: '{phrase}'.",
                    location=f"{readme_path.name}",
                    expected="Clean technical prose without template filler or marketing pleas",
                    actual=phrase,
                    suggested_fix=f"Remove '{phrase}' to maintain house style tone.",
                )

    def _check_badge_noise(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag badge flood (anti-pattern from NLP-Proj with 9+ noisy badges)."""
        badge_count = len(re.findall(r"img\.shields\.io/badge", text))
        if badge_count > MAX_BADGE_COUNT:
            report.add_finding(
                category=FindingCategory.VOICE_SLOP,
                severity=FindingSeverity.MINOR,
                message=f"Excessive badges ({badge_count} badges, max recommended {MAX_BADGE_COUNT}). Visual noise degrades readability.",
                location=f"{readme_path.name}",
                expected=f"<= {MAX_BADGE_COUNT} high-signal badges linking to evidence",
                actual=f"{badge_count} badges",
                suggested_fix="Prune vanity badges and keep only badges linked to verifiable evidence.",
            )

    def _check_badge_styles(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag noisy badge styles like 'for-the-badge' from NLP-Proj."""
        for style in FORBIDDEN_BADGE_STYLES:
            if f"style={style}" in text:
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.MINOR,
                    message=f"Forbidden badge style '{style}' detected (visual noise). House style mandates 'flat-square'.",
                    location=f"{readme_path.name}",
                    expected="style=flat-square",
                    actual=f"style={style}",
                    suggested_fix="Replace 'style=for-the-badge' with 'style=flat-square'.",
                )

    def _check_house_style_sections(
        self,
        text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Verify presence of core house style sections (duet/body2health model)."""
        checks = [
            ("header_centered", r'<h1\s+align=["\']center["\']>', "Centered <h1> title header"),
            ("italic_hook", r'(?:<p\s+align=["\']center["\']>\s*<em>|\*[\w\s,–—\'-]+\*)', "Italic 1-line hook"),
            ("quickstart", r'##\s+Quickstart', "Quickstart section"),
            ("evidence_grounding", r'##\s+Evidence', "Evidence & Ground Truth section"),
            ("deliberate_omissions", r'##\s+Deliberately not included', "Deliberately not included tradeoff notes"),
        ]

        for sec_id, pat, description in checks:
            if not re.search(pat, text, re.IGNORECASE):
                report.add_finding(
                    category=FindingCategory.VOICE_SLOP,
                    severity=FindingSeverity.MINOR,
                    message=f"Missing recommended house style element: {description}.",
                    location=f"{readme_path.name}",
                    expected=description,
                    actual="Missing section",
                    suggested_fix=f"Add '{description}' following the duet/body2health house style rubric.",
                )

    def sanitize(self, text: str) -> str:
        """Heuristic auto-cleaner to strip blatant AI filler and template greetings."""
        cleaned = text
        for phrase in AI_THROAT_CLEARING:
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b,?\s*", "", cleaned, flags=re.IGNORECASE)

        for slop in ["Welcome to ", "Hey there! ", "Happy coding! ", "⭐ Star us on GitHub", "Star us on GitHub", "Feel free to contribute"]:
            cleaned = re.sub(rf"{re.escape(slop)}", "", cleaned, flags=re.IGNORECASE)

        for forbidden in FORBIDDEN_PHRASES:
            cleaned = re.sub(rf"{re.escape(forbidden)}", "", cleaned, flags=re.IGNORECASE)

        return cleaned

