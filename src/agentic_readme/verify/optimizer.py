"""Evaluator-Optimizer loop for Phase 2 Verification.

Executes cross-asset verification across Claim Auditor, Render Checker, and
Voice Editor, running up to 2 optimization passes to fix detected discrepancies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from agentic_readme.core.models import (
    FactsLedger,
    FindingCategory,
    FindingSeverity,
    StorySpec,
    VerificationReport,
)
from agentic_readme.verify.claim_auditor import ClaimAuditor
from agentic_readme.verify.render_checker import RenderChecker
from agentic_readme.verify.voice_editor import VoiceEditor


class EvaluatorOptimizer:
    """Evaluates generated assets and applies targeted fixes up to max 2 rounds."""

    def __init__(self, repo_dir: Path, ledger: FactsLedger):
        self.repo_dir = Path(repo_dir)
        self.ledger = ledger
        self.auditor = ClaimAuditor(ledger)
        self.render_checker = RenderChecker(self.repo_dir)
        self.voice_editor = VoiceEditor()

    def run_loop(
        self,
        readme_path: Path,
        story: StorySpec,
        max_rounds: int = 2,
    ) -> Tuple[VerificationReport, bool]:
        report = VerificationReport()

        for round_idx in range(1, max_rounds + 1):
            # Run all 3 evaluators
            current_report = VerificationReport()
            self.auditor.audit(readme_path, story, current_report)
            self.render_checker.check(readme_path, current_report)
            self.voice_editor.check(readme_path, current_report)

            # If clean or only minor warnings, we're done
            if current_report.fatal_count == 0 and current_report.warning_count == 0:
                return current_report, True

            # If last round, record findings and stop
            if round_idx == max_rounds:
                return current_report, (current_report.fatal_count == 0)

            # Apply automatic optimizer fixes to readme_path
            self._apply_auto_fixes(readme_path, current_report)

        return current_report, (current_report.fatal_count == 0)

    def _apply_auto_fixes(self, readme_path: Path, report: VerificationReport) -> None:
        """Apply deterministic fixes for common drift and render issues."""
        text = readme_path.read_text(encoding="utf-8", errors="ignore")

        # 1. Fix fact drift on test counts
        test_fact = self.ledger.get_fact("test_count")
        if test_fact:
            expected_tests = str(test_fact.value)
            # Fix badge drift
            text = re.sub(r"(?:tests?|pytest)-\d+(%20|\s+|-)?(?:passed)?", f"tests-{expected_tests}%20passed", text, flags=re.IGNORECASE)
            # Fix body text drift
            for finding in report.findings:
                if finding.category == FindingCategory.FACT_DRIFT and finding.actual:
                    if finding.actual.isdigit():
                        text = re.sub(rf"\b{finding.actual}\s+(?:passing\s+|unit\s+)?tests?\b", f"{expected_tests} tests", text)

        # Fix fact drift on LOC
        loc_fact = self.ledger.get_fact("python_loc")
        if loc_fact:
            expected_loc = str(loc_fact.value)
            text = re.sub(r"\bloc:\s*\d+\b", f"loc: {expected_loc}", text)
            for finding in report.findings:
                if finding.category == FindingCategory.FACT_DRIFT and finding.actual:
                    if finding.actual.isdigit() and "lines of code" in finding.message:
                        text = re.sub(rf"\b{finding.actual}\s+lines of code\b", f"{expected_loc} lines of code", text)

        # 2. Fix license badge drift
        lic_fact = self.ledger.get_fact("license")
        if lic_fact:
            expected_lic = str(lic_fact.value)
            text = re.sub(r"badge/licen[sc]e-[a-zA-Z0-9\.\_\-]+", f"badge/license-{expected_lic}", text, flags=re.IGNORECASE)

        # 3. Fix Python version badge drift
        py_fact = self.ledger.get_fact("python_version")
        if py_fact:
            expected_py = str(py_fact.value).replace(" ", "%20")
            text = re.sub(r"badge/python-[0-9\.\+\>\<=\^%]+", f"badge/python-{expected_py}", text, flags=re.IGNORECASE)

        # 4. Fix GitHub relative <video> tags
        for finding in report.findings:
            if finding.category == FindingCategory.RENDER_ISSUE and ("<video" in (finding.actual or "") or "<source" in (finding.actual or "")):
                # Match <video ...> ... </video> or <video .../>
                def _video_repl(match):
                    full_match = match.group(0)
                    src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', full_match, re.IGNORECASE)
                    poster_m = re.search(r'\bposter=["\']([^"\']+)["\']', full_match, re.IGNORECASE)
                    video_src = src_m.group(1) if src_m else "demo.mp4"
                    poster_src = poster_m.group(1) if poster_m else "assets/demo/hero-demo.svg"
                    return (
                        f'<p align="center">\n'
                        f'  <a href="{video_src}">\n'
                        f'    <img alt="Click to launch MP4 preview" src="{poster_src}" width="760">\n'
                        f'  </a><br>\n'
                        f'  <sub><a href="{video_src}">▶ Download or view video directly ({video_src})</a></sub>\n'
                        f'</p>'
                    )

                text = re.sub(
                    r'<video[^>]*>[\s\S]*?</video>|<video[^>]*/>',
                    _video_repl,
                    text,
                    flags=re.IGNORECASE,
                )

        # 5. Fix badge styles (replace noisy for-the-badge with flat-square)
        text = text.replace("style=for-the-badge", "style=flat-square")

        # 6. Sanitize voice and AI throat-clearing
        text = self.voice_editor.sanitize(text)

        # 7. Remove leaked jargon
        for finding in report.findings:
            if finding.category == FindingCategory.JARGON_LEAKAGE and finding.actual:
                text = text.replace(finding.actual, "")

        readme_path.write_text(text, encoding="utf-8")

