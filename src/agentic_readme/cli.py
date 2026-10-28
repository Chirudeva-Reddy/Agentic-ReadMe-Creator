"""Command-line interface for Agentic ReadMe Creator.

Every pipeline command runs on LangGraph and is traced to LangSmith and Langfuse when
their credentials are set (see core/observability.py):
- ground: Phase 0 inspection and contract generation
- produce: Phase 1 parallel asset generation
- verify: Phase 2 claim auditing and render verification
- run: End-to-end pipeline, with an optional human gate and Claude polish
- audit: Standalone audit of an existing README against facts.json
- agent: a LangChain tool-calling agent over the pipeline tools
- eval: evaluation of the pipeline over the committed examples (local, LangSmith, or Langfuse)
"""

from __future__ import annotations

import atexit
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentic_readme.core import observability
from agentic_readme.core.models import FactsLedger, StorySpec, VerificationReport
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

# Traces are batched in the background; send what is left when the command exits.
atexit.register(observability.flush)


def _report_tracing() -> None:
    backends = observability.enabled_backends()
    if backends:
        observability.flush()
        console.print(f"Tracing on: {', '.join(backends)} (upload errors, if any, are logged above).")


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
    _report_tracing()


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
    _report_tracing()


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
    _report_tracing()

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

    report = VerificationReport()

    auditor.audit(readme_path, report=report)
    render_checker.check(readme_path, report=report)
    voice_editor.check(readme_path, report=report)

    _display_report(report)
    if not report.passed:
        raise typer.Exit(code=1)


def _confirm_gate(payload) -> bool:
    console.print(f"[bold yellow]⏸ HUMAN GATE:[/bold yellow] {payload['question']}")
    console.print(f"  story: {payload['story']}\n  facts: {payload['facts']}")
    return typer.confirm("Produce the README from these contracts?", default=True)


@app.command()
def run(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    auto_approve: bool = typer.Option(True, "--auto-approve/--review", help="--review pauses after grounding so you can edit story.yaml, then confirm"),
    polish: bool = typer.Option(False, "--polish", help="Rewrite the story's hook, problem, and solution with Claude (needs ANTHROPIC_API_KEY)"),
    audience: Optional[str] = typer.Option(None, "--audience", "-a", help="Target audience description"),
    hook: Optional[str] = typer.Option(None, "--hook", help="Custom 1-line pain hook"),
):
    """Run the full pipeline graph (Ground -> Human Gate -> Produce -> Verify)."""
    runner = PipelineRunner(repo_path, output_dir=output_dir)
    res = runner.run_all(
        auto_approve_gate=auto_approve, approve=_confirm_gate, polish=polish, target_audience=audience, custom_hook=hook
    )
    _report_tracing()
    if not res["approved"]:
        console.print("[yellow]Stopped at the human gate. Nothing was produced.[/yellow]")
        raise typer.Exit(code=1)

    _display_report(res["verification_report"])
    if not res["passed"]:
        raise typer.Exit(code=1)


@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) stdio server for Claude, GPT, and Cursor."""
    from agentic_readme.mcp import run_mcp_server
    run_mcp_server()


@app.command()
def agent(
    prompt: str = typer.Argument(..., help='What to do, e.g. "write and verify the README for examples/tip-splitter"'),
):
    """Ask a Claude agent (LangChain) to run the pipeline tools for you. Needs ANTHROPIC_API_KEY."""
    from agentic_readme.orchestrate.tools import build_agent

    try:
        with observability.trace_run("readme-agent", inputs={"prompt": prompt}, tags=["agent"]) as run:
            result = build_agent().invoke({"messages": [{"role": "user", "content": prompt}]}, run.config)
            run.set_output({"answer": result["messages"][-1].text})
    except Exception as exc:  # missing credentials, network, API errors
        console.print(f"[red]Agent failed: {exc.__class__.__name__}: {exc}[/red]")
        raise typer.Exit(code=1)

    console.print(result["messages"][-1].text)
    _report_tracing()


@app.command(name="eval")
def evaluate(
    examples_dir: Path = typer.Option(Path("examples"), "--examples", "-e", help="Folder of example projects with committed .agentic-readme/facts.json"),
    langsmith: bool = typer.Option(False, "--langsmith", help="Upload the dataset and record an experiment in LangSmith (needs LANGSMITH_API_KEY)"),
    langfuse: bool = typer.Option(False, "--langfuse", help="Upload the dataset and record an experiment in Langfuse (needs LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)"),
):
    """Run the pipeline on every example and score it (verification passed, clean first pass, test count)."""
    from agentic_readme.orchestrate import evaluation

    if langsmith:
        results = evaluation.run_langsmith_evaluation(examples_dir)
        console.print(f"LangSmith experiment: [bold]{results.experiment_name}[/bold]")
    if langfuse:
        result = evaluation.run_langfuse_evaluation(examples_dir)
        console.print(f"Langfuse experiment: [bold]{result.run_name}[/bold] {result.experiment_url or ''}")
    if langsmith or langfuse:
        return

    results = evaluation.run_local_evaluation(examples_dir)
    if not results:
        console.print(f"[red]No examples with .agentic-readme/facts.json under {examples_dir}[/red]")
        raise typer.Exit(code=1)

    keys = list(results[0]["scores"])
    table = Table(title="Graph evaluation")
    table.add_column("Example", style="cyan")
    for key in keys:
        table.add_column(key)
    for row in results:
        table.add_row(row["example"], *("[green]pass[/green]" if row["scores"][k] else "[red]fail[/red]" for k in keys))
    console.print(table)

    if not all(all(row["scores"].values()) for row in results):
        raise typer.Exit(code=1)


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
