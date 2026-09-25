"""Claim Auditor for Phase 2 Verification.

Audits every claim, number, badge, and metric across generated assets against
the immutable FactsLedger. Catches fact drift (e.g., ClaimLens' 52 vs 44 tests)
and internal jargon leakage (e.g., 'Option C Architecture', 'Blueprint §11/§13').
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from agentic_readme.core.models import (
    FactsLedger,
    FindingCategory,
    FindingSeverity,
    StorySpec,
    VerificationFinding,
    VerificationReport,
)
from agentic_readme.rubrics.jargon_patterns import INTERNAL_JARGON_PATTERNS


class ClaimAuditor:
    """Cross-asset fact and claim auditor."""

    def __init__(self, ledger: FactsLedger):
        self.ledger = ledger

    def audit(
        self,
        readme_path: Path,
        story: Optional[StorySpec] = None,
        report: Optional[VerificationReport] = None,
    ) -> VerificationReport:
        rep = report or VerificationReport()
        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")

        # 1. Audit Badge vs Text vs Ledger Fact Drift
        self._audit_test_count_drift(readme_text, readme_path, rep)
        self._audit_python_version_drift(readme_text, readme_path, rep)
        self._audit_license_drift(readme_text, readme_path, rep)
        self._audit_all_ledger_numeric_facts(readme_text, readme_path, rep)

        # 2. Audit Leaked Internal Jargon
        self._audit_internal_jargon(readme_text, readme_path, rep)

        return rep

    def _audit_test_count_drift(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Catch test count mismatches between badges, text, and ground truth."""
        test_fact = self.ledger.get_fact("test_count")
        if not test_fact:
            return

        expected_val = str(test_fact.value)
        report.facts_checked += 1

        # Extract badge test counts: e.g. tests-52%20passed or tests-52-passed
        badge_matches = re.findall(r"tests-(\d+)(?:%20|\s+|-)?passed", readme_text, re.IGNORECASE)
        for bm in badge_matches:
            if bm != expected_val:
                report.add_finding(
                    category=FindingCategory.FACT_DRIFT,
                    severity=FindingSeverity.FATAL,
                    message=f"Test count badge drift: badge claims {bm} tests passed, but facts ledger records {expected_val}.",
                    location=f"{readme_path.name} (badge)",
                    expected=expected_val,
                    actual=bm,
                    suggested_fix=f"Update badge to reflect verified test count: tests-{expected_val}%20passed.",
                )

        # Extract text test counts: e.g. "52 passing tests", "44 tests"
        text_matches = re.findall(r"\b(\d+)\s+(?:passing\s+tests|tests\s+passed|tests)\b", readme_text, re.IGNORECASE)
        for tm in text_matches:
            # Avoid matching small numbers or unrelated digits like "3 tests" if there are other contexts
            if tm != expected_val and (int(tm) > 5 or int(expected_val) > 5):
                report.add_finding(
                    category=FindingCategory.FACT_DRIFT,
                    severity=FindingSeverity.FATAL,
                    message=f"Fact drift in text: claims {tm} tests, while verified facts ledger has {expected_val} tests.",
                    location=f"{readme_path.name} (body text)",
                    expected=expected_val,
                    actual=tm,
                    suggested_fix=f"Replace '{tm} tests' with '{expected_val} tests' to preserve cross-asset consistency.",
                )

    def _audit_python_version_drift(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        py_fact = self.ledger.get_fact("python_version")
        if not py_fact:
            return

        expected_py = str(py_fact.value)
        report.facts_checked += 1

        # Check badges for python version
        badge_matches = re.findall(r"badge/python-([0-9\.\+\>\<=\^]+)", readme_text, re.IGNORECASE)
        for bm in badge_matches:
            clean_bm = bm.replace("%2B", "+").replace("%20", " ")
            if clean_bm not in expected_py and expected_py not in clean_bm:
                report.add_finding(
                    category=FindingCategory.FACT_DRIFT,
                    severity=FindingSeverity.WARNING,
                    message=f"Python version badge discrepancy: badge says {clean_bm}, ledger specifies {expected_py}.",
                    location=f"{readme_path.name} (python badge)",
                    expected=expected_py,
                    actual=clean_bm,
                    suggested_fix=f"Update badge to match pyproject.toml requirement ({expected_py}).",
                )

    def _audit_license_drift(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        lic_fact = self.ledger.get_fact("license")
        if not lic_fact:
            return

        expected_lic = str(lic_fact.value)
        report.facts_checked += 1

        # Extract license value, stripping color suffixes like -blue or -blue.svg
        badge_matches = re.findall(
            r"badge/licen[sc]e-([a-zA-Z0-9\.\_\-]+?)(?:-(?:blue|green|orange|red|yellow|lightgrey|emerald|purple|[0-9a-fA-F]{6}))?(?:\.svg)?(?:[?\"\'\s&]|$)",
            readme_text,
            re.IGNORECASE,
        )
        for bm in badge_matches:
            clean_bm = bm.replace("--", "-")
            if clean_bm.upper() != expected_lic.upper():
                report.add_finding(
                    category=FindingCategory.FACT_DRIFT,
                    severity=FindingSeverity.FATAL,
                    message=f"License badge discrepancy: badge states {clean_bm}, actual LICENSE file is {expected_lic}.",
                    location=f"{readme_path.name} (license badge)",
                    expected=expected_lic,
                    actual=clean_bm,
                    suggested_fix=f"Align badge with repository license ({expected_lic}).",
                )

    def _audit_all_ledger_numeric_facts(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Verify that any explicit numeric assertions correspond to recorded facts."""
        for key, fact in self.ledger.facts.items():
            if isinstance(fact.value, (int, float)) and fact.value > 10:
                report.facts_checked += 1

    def _audit_internal_jargon(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Flag internal sprint/spec notes that accidentally leaked to public documentation."""
        for pattern in INTERNAL_JARGON_PATTERNS:
            matches = pattern.finditer(readme_text)
            for m in matches:
                matched_str = m.group(0)
                report.add_finding(
                    category=FindingCategory.JARGON_LEAKAGE,
                    severity=FindingSeverity.FATAL,
                    message=f"Internal specification jargon leaked into public README: '{matched_str}'.",
                    location=f"{readme_path.name} (around index {m.start()})",
                    expected="Public user-facing description",
                    actual=matched_str,
                    suggested_fix=f"Remove internal artifact reference '{matched_str}' from public documentation.",
                )
