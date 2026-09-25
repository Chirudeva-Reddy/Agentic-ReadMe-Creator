"""End-to-end Pipeline Runner for Agentic ReadMe Creator.

Orchestrates the 3-phase flow:
- Phase 0: Ground (RepoAnalyst -> story.yaml & facts.json)
- Human Gate (Approval / editing of narrative & facts)
- Phase 1: Produce (DiagramAgent, DemoAgent, VideoAgent, WriterAgent)
- Phase 2: Verify (EvaluatorOptimizer: ClaimAuditor, RenderChecker, VoiceEditor)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from rich.console import Console

from agentic_readme.core.models import FactsLedger, StorySpec, VerificationReport
from agentic_readme.ground.repo_analyst import RepoAnalyst
from agentic_readme.ground.story_builder import StoryBuilder
from agentic_readme.produce.demo_agent import DemoAgent
from agentic_readme.produce.diagram_agent import DiagramAgent
from agentic_readme.produce.video_agent import VideoAgent
from agentic_readme.produce.writer_agent import WriterAgent
from agentic_readme.verify.optimizer import EvaluatorOptimizer

console = Console()


class PipelineRunner:
    """Coordinates execution across Phase 0, Phase 1, and Phase 2."""

    def __init__(self, repo_path: Path, output_dir: Optional[Path] = None):
        self.repo_path = Path(repo_path).resolve()
        self.output_dir = Path(output_dir or self.repo_path).resolve()

    def phase_0_ground(self, target_audience: Optional[str] = None, custom_hook: Optional[str] = None) -> Tuple[StorySpec, FactsLedger]:
        """Phase 0: Ground repo facts and narrative into immutable contracts."""
        console.print(f"[bold cyan][Phase 0: GROUND][/bold cyan] Analyzing repository at {self.repo_path}...")

        analyst = RepoAnalyst(self.repo_path)
        analysis = analyst.analyze()

        builder = StoryBuilder(analysis)
        story = builder.build_story(target_audience=target_audience, custom_hook=custom_hook)
        ledger = analysis.facts_ledger

        # Save contracts
        story_file = self.output_dir / "story.yaml"
        facts_file = self.output_dir / "facts.json"

        story.save_yaml(story_file)
        ledger.save(facts_file)

        console.print(f"[green]✔ Locked contracts created:[/green]")
        console.print(f"  - Story Spec: [bold]{story_file}[/bold]")
        console.print(f"  - Facts Ledger: [bold]{facts_file}[/bold] ({len(ledger.facts)} facts recorded)")

        return story, ledger

    def phase_1_produce(self, story: StorySpec, ledger: FactsLedger) -> Dict[str, Any]:
        """Phase 1: Fan-out producers reading immutable story and facts."""
        console.print(f"[bold cyan][Phase 1: PRODUCE][/bold cyan] Generating assets from locked story & facts...")

        # 1. Diagram Agent
        diagram_agent = DiagramAgent(self.output_dir)
        diagram_assets = diagram_agent.produce(story, ledger)
        console.print("  [green]✔ Diagram Agent:[/green] generated .excalidraw + light/dark SVGs")

        # 2. Demo Agent
        demo_agent = DemoAgent(self.output_dir)
        demo_assets = demo_agent.produce(story, ledger)
        console.print("  [green]✔ Demo Agent:[/green] generated VHS script + hero asset")

        # 3. Video Agent
        video_agent = VideoAgent(self.output_dir)
        video_assets = video_agent.produce(story, ledger)
        console.print("  [green]✔ Video Agent:[/green] generated /brag 20s spec + scene table")

        # 4. Writer Agent
        writer_agent = WriterAgent(self.output_dir)
        readme_path = writer_agent.produce(story, ledger)
        console.print("  [green]✔ Writer Agent:[/green] generated candidate README.md")

        return {
            "diagrams": diagram_assets,
            "demo": demo_assets,
            "video": video_assets,
            "readme": readme_path,
        }

    def phase_2_verify(self, story: StorySpec, ledger: FactsLedger) -> Tuple[VerificationReport, bool]:
        """Phase 2: Evaluator-Optimizer loop verifying cross-asset facts and rendering."""
        console.print(f"[bold cyan][Phase 2: VERIFY][/bold cyan] Running cross-asset verification & claim auditing...")

        readme_path = self.output_dir / "README.md"
        optimizer = EvaluatorOptimizer(self.output_dir, ledger)
        report, passed = optimizer.run_loop(readme_path, story, max_rounds=2)

        if passed:
            console.print(f"[green]✔ Verification PASSED[/green] ({report.facts_checked} facts checked, 0 fatal bugs)")
        else:
            console.print(f"[yellow]⚠ Verification finished with {report.fatal_count} fatal findings[/yellow]")

        return report, passed

    def run_all(self, auto_approve_gate: bool = True) -> Dict[str, Any]:
        """Full pipeline execution with Human Gate."""
        # Phase 0
        story, ledger = self.phase_0_ground()

        # Human Gate
        if not auto_approve_gate:
            console.print("[bold yellow]⏸ HUMAN GATE: Please inspect story.yaml and facts.json before continuing.[/bold yellow]")

        # Phase 1
        produced_assets = self.phase_1_produce(story, ledger)

        # Phase 2
        report, passed = self.phase_2_verify(story, ledger)

        return {
            "story": story,
            "facts": ledger,
            "assets": produced_assets,
            "verification_report": report,
            "passed": passed,
        }
