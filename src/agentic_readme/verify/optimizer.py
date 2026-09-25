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
            text = re.sub(r"tests-\d+(%20|\s+|-)?passed", f"tests-{expected_tests}%20passed", text, flags=re.IGNORECASE)
            # Fix body text drift
            for finding in report.findings:
                if finding.category == FindingCategory.FACT_DRIFT and finding.actual:
                    if finding.actual.isdigit():
                        text = re.sub(rf"\b{finding.actual}\s+tests\b", f"{expected_tests} tests", text)

        # 2. Fix GitHub relative <video> tags
        for finding in report.findings:
            if finding.category == FindingCategory.RENDER_ISSUE and "<video" in finding.actual:
                # Replace relative <video ... src="path.mp4"> with a GIF preview linking to MP4
                text = re.sub(
                    r'<video[^>]*\bsrc=["\']([^"\']+\.mp4)["\'][^>]*>[\s\S]*?</video>',
                    r'<p align="center"><a href="\1"><img alt="Click to launch MP4 preview" src="assets/demo/hero-demo.svg" width="760"></a><br><sub><a href="\1">▶ Download or view video directly (\1)</a></sub></p>',
                    text,
                    flags=re.IGNORECASE,
                )

        # 3. Sanitize voice and AI throat-clearing
        text = self.voice_editor.sanitize(text)

        # 4. Remove leaked jargon
        for finding in report.findings:
            if finding.category == FindingCategory.JARGON_LEAKAGE and finding.actual:
                text = text.replace(finding.actual, "")

        readme_path.write_text(text, encoding="utf-8")
