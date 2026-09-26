"""Command-line interface for Agentic ReadMe Creator.

Supports modular execution of:
- ground: Phase 0 inspection and contract generation
- produce: Phase 1 parallel asset generation
- verify: Phase 2 claim auditing and render verification
- run: End-to-end automated pipeline
- audit: Standalone audit of an existing README against facts.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentic_readme.core.models import FactsLedger, StorySpec
from agentic_readme.core.runner import PipelineRunner, contract_path
from agentic_readme.verify.claim_auditor import ClaimAuditor
from agentic_readme.verify.render_checker import RenderChecker
from agentic_readme.verify.voice_editor import VoiceEditor

app = typer.Typer(
    name="agentic-readme",
    help="Verified, media-rich README pipeline grounded in real project runs.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def ground(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository to inspect"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for contracts"),
    audience: Optional[str] = typer.Option(None, "--audience", "-a", help="Target audience description"),
    hook: Optional[str] = typer.Option(None, "--hook", help="Custom 1-line pain hook"),
):
    """Phase 0: Ground repo facts into story.yaml and facts.json."""
    runner = PipelineRunner(repo_path, output_dir=output_dir)
    story, ledger = runner.phase_0_ground(target_audience=audience, custom_hook=hook)
    console.print(f"[bold green]Phase 0 complete.[/bold green] Inspect .agentic-readme/story.yaml and facts.json before producing.")


@app.command()
def produce(
    dir_path: Path = typer.Argument(Path("."), help="Project directory (contracts in .agentic-readme/)"),
):
    """Phase 1: Produce all media assets and README.md from locked story and facts."""
    story_file = contract_path(dir_path, "story.yaml")
    facts_file = contract_path(dir_path, "facts.json")

    if not story_file.exists() or not facts_file.exists():
        console.print("[red]Error: story.yaml or facts.json missing. Run 'ground' first.[/red]")
        raise typer.Exit(code=1)

    story = StorySpec.load_yaml(story_file)
    ledger = FactsLedger.load(facts_file)

    runner = PipelineRunner(dir_path, output_dir=dir_path)
    runner.phase_1_produce(story, ledger)
    console.print(f"[bold green]Phase 1 complete.[/bold green] Assets generated in assets/ and README.md.")


@app.command()
def verify(
    dir_path: Path = typer.Argument(Path("."), help="Project directory containing README.md and .agentic-readme/facts.json"),
):
    """Phase 2: Audit claims, check GitHub rendering rules, and clean voice."""
    story_file = contract_path(dir_path, "story.yaml")
    facts_file = contract_path(dir_path, "facts.json")

    if not facts_file.exists():
        console.print("[red]Error: facts.json missing. Cannot audit claims without ground truth.[/red]")
        raise typer.Exit(code=1)

    ledger = FactsLedger.load(facts_file)
    story = StorySpec.load_yaml(story_file) if story_file.exists() else None

    runner = PipelineRunner(dir_path, output_dir=dir_path)
    report, passed = runner.phase_2_verify(story, ledger)

    _display_report(report)
    if not passed:
        raise typer.Exit(code=1)


@app.command()
def audit(
    readme_path: Path = typer.Argument(..., help="Path to README.md to audit"),
    facts_file: Path = typer.Option(..., "--facts", "-f", help="Path to facts.json ground truth ledger"),
):
    """Standalone audit of an existing README against a facts ledger."""
    if not readme_path.exists():
        console.print(f"[red]Error: File not found: {readme_path}[/red]")
        raise typer.Exit(code=1)
    if not facts_file.exists():
        console.print(f"[red]Error: Facts file not found: {facts_file}[/red]")
        raise typer.Exit(code=1)

    ledger = FactsLedger.load(facts_file)
    auditor = ClaimAuditor(ledger)
    render_checker = RenderChecker(readme_path.parent)
    voice_editor = VoiceEditor()

    from agentic_readme.core.models import VerificationReport
    report = VerificationReport()

    auditor.audit(readme_path, report=report)
    render_checker.check(readme_path, report=report)
    voice_editor.check(readme_path, report=report)

    _display_report(report)
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def run(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    auto_approve: bool = typer.Option(True, "--auto-approve", help="Automatically approve Phase 0 gate"),
):
    """Run full 3-phase pipeline (Ground -> Produce -> Verify)."""
    runner = PipelineRunner(repo_path, output_dir=output_dir)
    res = runner.run_all(auto_approve_gate=auto_approve)
    report = res["verification_report"]
    _display_report(report)
    if not res["passed"]:
        raise typer.Exit(code=1)


@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) stdio server for Claude, GPT, and Cursor."""
    from agentic_readme.mcp import run_mcp_server
    run_mcp_server()


def _display_report(report) -> None:
    table = Table(title="Phase 2 Verification Report")
    table.add_column("Category", style="cyan")
    table.add_column("Severity", style="magenta")
    table.add_column("Finding / Drift", style="yellow")
    table.add_column("Location", style="white")

    for f in report.findings:
        sev_color = "red" if "Fatal" in f.severity else "yellow"
        table.add_row(
            f.category.value,
            f"[{sev_color}]{f.severity.value}[/{sev_color}]",
            f.message,
            f.location or "—",
        )

    console.print(table)
    console.print(f"Summary: [bold]{report.facts_checked}[/bold] facts checked. "
                  f"[bold red]{report.fatal_count} fatal errors[/bold red], "
                  f"[bold yellow]{report.warning_count} warnings[/bold yellow].")


if __name__ == "__main__":
    app()
