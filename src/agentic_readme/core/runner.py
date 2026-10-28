"""Python entry point for Agentic ReadMe Creator.

Each phase runs on the LangGraph graphs in orchestrate/graph.py:
- Phase 0: Ground (RepoAnalyst -> story.yaml & facts.json)
- Human Gate (LangGraph interrupt: approve or edit the contracts)
- Phase 1: Produce (DiagramAgent, DemoAgent, VideoAgent, WriterAgent, in parallel)
- Phase 2: Verify (Evaluator-Optimizer loop: ClaimAuditor, RenderChecker, VoiceEditor)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from rich.console import Console

from agentic_readme.core.contracts import CONTRACTS_DIR, contract_path
from agentic_readme.core.models import FactsLedger, StorySpec, VerificationReport
from agentic_readme.orchestrate.graph import ground_contracts, run_pipeline, run_produce, run_verify

__all__ = ["CONTRACTS_DIR", "PipelineRunner", "contract_path"]


class PipelineRunner:
    """Runs Phase 0, Phase 1, and Phase 2 on one repository."""

    def __init__(
        self,
        repo_path: Path,
        output_dir: Optional[Path] = None,
        console: Optional[Console] = None,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.output_dir = Path(output_dir or self.repo_path).resolve()
        self.console = console or Console(stderr=True)

    def phase_0_ground(self, target_audience: Optional[str] = None, custom_hook: Optional[str] = None) -> Tuple[StorySpec, FactsLedger]:
        """Phase 0: Ground repo facts and narrative into immutable contracts."""
        return ground_contracts(self.repo_path, self.output_dir, target_audience, custom_hook, console=self.console)

    def phase_1_produce(self, story: StorySpec, ledger: FactsLedger) -> Dict[str, Any]:
        """Phase 1: the four producers run in parallel on the locked story and facts."""
        return run_produce(self.output_dir, story, ledger, console=self.console)

    def phase_2_verify(self, story: Optional[StorySpec], ledger: FactsLedger) -> Tuple[VerificationReport, bool]:
        """Phase 2: Evaluator-Optimizer loop verifying cross-asset facts and rendering."""
        report, passed = run_verify(self.output_dir, story, ledger, console=self.console)
        if passed:
            self.console.print(f"[green]✔ Verification PASSED[/green] ({report.facts_checked} facts checked, 0 fatal bugs)")
        else:
            self.console.print(f"[yellow]⚠ Verification finished with {report.fatal_count} fatal findings[/yellow]")
        return report, passed

    def run_all(
        self,
        auto_approve_gate: bool = True,
        approve: Optional[Callable[[Dict[str, Any]], bool]] = None,
        polish: bool = False,
        llm: Optional[Any] = None,
        target_audience: Optional[str] = None,
        custom_hook: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full pipeline. With auto_approve_gate=False the run pauses after grounding and
        `approve(payload)` decides whether to continue; without a callback it stops there."""
        state = run_pipeline(
            self.repo_path,
            output_dir=self.output_dir,
            audience=target_audience,
            hook=custom_hook,
            polish=polish,
            review=not auto_approve_gate,
            approve=approve,
            llm=llm,
            console=self.console,
        )
        return {
            "story": StorySpec.load_yaml(contract_path(self.output_dir, "story.yaml")),
            "facts": FactsLedger.load(contract_path(self.output_dir, "facts.json")),
            "approved": state.get("approved", False),
            "assets": state.get("assets", {}),
            "verification_report": VerificationReport.model_validate(state["report"]) if state.get("report") else None,
            "passed": state.get("passed", False),
            "notes": state.get("notes", []),
        }
