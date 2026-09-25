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
from agentic_readme.rubrics.house_style import MAX_BADGE_COUNT
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
        self._check_badge_noise(readme_text, readme_path, rep)

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

    def sanitize(self, text: str) -> str:
        """Heuristic auto-cleaner to strip blatant AI filler and template greetings."""
        cleaned = text
        for phrase in AI_THROAT_CLEARING:
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b,?\s*", "", cleaned, flags=re.IGNORECASE)

        for slop in ["Welcome to ", "Hey there! ", "Happy coding! "]:
            cleaned = re.sub(rf"{re.escape(slop)}", "", cleaned, flags=re.IGNORECASE)

        return cleaned
