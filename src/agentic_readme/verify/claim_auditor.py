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
    """Cross-asset fact, metric, and claim auditor."""

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
        repo_dir = readme_path.parent

        # 1. Audit Badge vs Text vs Ledger Fact Drift in README
        self._audit_test_count_drift(readme_text, readme_path, rep)
        self._audit_python_version_drift(readme_text, readme_path, rep)
        self._audit_project_version_drift(readme_text, readme_path, rep)
        self._audit_license_drift(readme_text, readme_path, rep)
        self._audit_all_ledger_numeric_facts(readme_text, readme_path, rep)

        # 2. Audit Leaked Internal Jargon in README
        self._audit_internal_jargon(readme_text, readme_path, rep)

        # 3. Cross-Asset Verification (Video spec, demo tape, Excalidraw, scene table)
        self._audit_cross_assets(repo_dir, rep)

        # 4. Audit Badge Evidence Links
        self._audit_badge_evidence_links(readme_text, repo_dir, rep)

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

        # Extract badge test counts: e.g. tests-52%20passed or pytest-52-passed or tests-52
        badge_matches = re.findall(r"(?:tests?|pytest)-(\d+)(?:%20|\s+|-)?(?:passed)?", readme_text, re.IGNORECASE)
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

        # Extract text test counts: e.g. "52 passing tests", "44 tests", "52 unit tests"
        text_matches = re.findall(
            r"\b(\d+)\s+(?:passing\s+tests|tests\s+passed|tests|pytest\s+cases|unit\s+tests)\b",
            readme_text,
            re.IGNORECASE,
        )
        for tm in text_matches:
            if tm != expected_val:
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

    def _audit_project_version_drift(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        ver_fact = self.ledger.get_fact("project_version") or self.ledger.get_fact("package_version") or self.ledger.get_fact("cargo_version")
        if not ver_fact:
            return

        expected_ver = str(ver_fact.value)
        report.facts_checked += 1

        # Check badges for version: badge/version-0.1.0 or badge/crates.io-v0.1.0
        badge_matches = re.findall(r"badge/(?:version|release|v)-v?([0-9\.]+)", readme_text, re.IGNORECASE)
        for bm in badge_matches:
            if bm != expected_ver:
                report.add_finding(
                    category=FindingCategory.FACT_DRIFT,
                    severity=FindingSeverity.WARNING,
                    message=f"Version badge discrepancy: badge says v{bm}, ledger specifies {expected_ver}.",
                    location=f"{readme_path.name} (version badge)",
                    expected=expected_ver,
                    actual=bm,
                    suggested_fix=f"Update badge to match project version ({expected_ver}).",
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
        """Verify explicit numeric assertions in README against recorded benchmark metrics."""
        for key, fact in self.ledger.facts.items():
            report.facts_checked += 1
            if not key.startswith("metric_"):
                continue

            metric_name = key.replace("metric_", "")
            val = fact.value
            if isinstance(val, (int, float)):
                # Search for metric name near conflicting numeric value in text
                pattern = re.compile(
                    rf"\b{re.escape(metric_name)}\b[^\n\.\,]{{0,35}}(\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                )
                for m in pattern.finditer(readme_text):
                    claimed_num = float(m.group(1))
                    actual_num = float(val)
                    # Check relative error > 10%
                    if actual_num > 0 and abs(claimed_num - actual_num) / actual_num > 0.10:
                        report.add_finding(
                            category=FindingCategory.FACT_DRIFT,
                            severity=FindingSeverity.WARNING,
                            message=f"Metric discrepancy for '{metric_name}': claims {claimed_num}, ledger records {actual_num}.",
                            location=f"{readme_path.name} (around index {m.start()})",
                            expected=str(actual_num),
                            actual=str(claimed_num),
                            suggested_fix=f"Update '{metric_name}' in documentation to match ledger value ({actual_num}).",
                        )

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
                    message=f"Internal specification jargon leaked into public documentation: '{matched_str}'.",
                    location=f"{readme_path.name} (around index {m.start()})",
                    expected="Public user-facing description",
                    actual=matched_str,
                    suggested_fix=f"Remove internal artifact reference '{matched_str}' from public documentation.",
                )

    def _audit_cross_assets(
        self,
        repo_dir: Path,
        report: VerificationReport,
    ) -> None:
        """Audit non-README generated assets for fact drift and jargon leakage."""
        test_fact = self.ledger.get_fact("test_count")
        expected_tests = str(test_fact.value) if test_fact else None

        # 1. Audit assets/video/brag_spec.json
        brag_spec = repo_dir / "assets" / "video" / "brag_spec.json"
        if brag_spec.exists():
            report.facts_checked += 1
            content = brag_spec.read_text(encoding="utf-8", errors="ignore")
            # Check internal jargon
            for pattern in INTERNAL_JARGON_PATTERNS:
                m = pattern.search(content)
                if m:
                    report.add_finding(
                        category=FindingCategory.JARGON_LEAKAGE,
                        severity=FindingSeverity.FATAL,
                        message=f"Internal jargon leaked into /brag launch video spec: '{m.group(0)}'.",
                        location="assets/video/brag_spec.json",
                        expected="Clean public launch narration",
                        actual=m.group(0),
                        suggested_fix="Sanitize /brag launch video storyboard.",
                    )
            # Check test drift in brag narration
            if expected_tests:
                matches = re.findall(r"\b(\d+)\s+tests?\b", content, re.IGNORECASE)
                for tm in matches:
                    if tm != expected_tests:
                        report.add_finding(
                            category=FindingCategory.FACT_DRIFT,
                            severity=FindingSeverity.FATAL,
                            message=f"Test count drift in /brag video spec: claims {tm} tests, facts ledger has {expected_tests}.",
                            location="assets/video/brag_spec.json",
                            expected=expected_tests,
                            actual=tm,
                            suggested_fix=f"Synchronize video narration with facts ledger ({expected_tests} tests).",
                        )

        # 2. Audit assets/video/scenes.md
        scenes_file = repo_dir / "assets" / "video" / "scenes.md"
        if scenes_file.exists():
            report.facts_checked += 1
            content = scenes_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in INTERNAL_JARGON_PATTERNS:
                m = pattern.search(content)
                if m:
                    report.add_finding(
                        category=FindingCategory.JARGON_LEAKAGE,
                        severity=FindingSeverity.FATAL,
                        message=f"Internal jargon leaked into video scene table: '{m.group(0)}'.",
                        location="assets/video/scenes.md",
                        expected="Clean scene table",
                        actual=m.group(0),
                    )

        # 3. Audit assets/diagrams/architecture.excalidraw
        excal_file = repo_dir / "assets" / "diagrams" / "architecture.excalidraw"
        if excal_file.exists():
            report.facts_checked += 1
            content = excal_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in INTERNAL_JARGON_PATTERNS:
                m = pattern.search(content)
                if m:
                    report.add_finding(
                        category=FindingCategory.JARGON_LEAKAGE,
                        severity=FindingSeverity.FATAL,
                        message=f"Internal jargon found in architecture diagram: '{m.group(0)}'.",
                        location="assets/diagrams/architecture.excalidraw",
                        expected="Clean architectural component label",
                        actual=m.group(0),
                    )

        # 4. Audit assets/demo/demo.tape
        tape_file = repo_dir / "assets" / "demo" / "demo.tape"
        if tape_file.exists():
            report.facts_checked += 1
            content = tape_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in INTERNAL_JARGON_PATTERNS:
                m = pattern.search(content)
                if m:
                    report.add_finding(
                        category=FindingCategory.JARGON_LEAKAGE,
                        severity=FindingSeverity.FATAL,
                        message=f"Internal jargon found in demo.tape: '{m.group(0)}'.",
                        location="assets/demo/demo.tape",
                        expected="Clean CLI commands",
                        actual=m.group(0),
                    )

    def _audit_badge_evidence_links(
        self,
        readme_text: str,
        repo_dir: Path,
        report: VerificationReport,
    ) -> None:
        """Verify that badges wrap links to actual evidence files in the repo."""
        badge_links = re.finditer(r'<a\s+href=["\']([^"\']+)["\']>\s*<img[^>]*badge[^>]*>\s*</a>', readme_text, re.IGNORECASE)
        for bl in badge_links:
            href = bl.group(1).split("#")[0].strip()
            report.facts_checked += 1
            # If relative path, check that evidence file exists
            if not href.startswith("http://") and not href.startswith("https://") and href:
                target = (repo_dir / href).resolve()
                if not target.exists():
                    report.add_finding(
                        category=FindingCategory.FACT_DRIFT,
                        severity=FindingSeverity.WARNING,
                        message=f"Badge links to missing evidence target: '{href}'. Badges must link to real evidence.",
                        location="README.md (badge link)",
                        expected="Existing file or directory in repository",
                        actual=href,
                        suggested_fix=f"Update badge href to link to an existing evidence file or test directory.",
                    )

