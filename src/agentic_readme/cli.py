"""The `agentic-readme` command: the front door for humans and CI.

Each command is a thin wrapper around one function in pipeline.py:

    ground   -> pipeline.ground     write facts.json + story.yaml
    produce  -> pipeline.produce    write README.md + assets/
    verify   -> pipeline.verify     check, auto-fix, check again; exit 1 on fatal findings
    audit    -> pipeline.check      read-only check of any README; exit 1 on fatal findings
    run      -> pipeline.run        all three steps
    mcp      -> mcp.run_mcp_server  the same tools for AI assistants (JSON-RPC over stdio)

Typer turns each decorated function into a sub-command and its arguments into options.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agentic_readme import pipeline
from agentic_readme.models import FactsLedger, FindingSeverity, VerificationReport

app = typer.Typer(
    name="agentic-readme",
    help="Verified, media-rich README pipeline grounded in real project runs.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def ground(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository to inspect"),
    output_dir: Path | None = typer.Option(None, "--output", "-o", help="Output directory for contracts"),
    audience: str | None = typer.Option(None, "--audience", "-a", help="Target audience description"),
    hook: str | None = typer.Option(None, "--hook", help="Custom 1-line pain hook"),
):
    """Phase 0: Ground repo facts into story.yaml and facts.json."""
    pipeline.ground(repo_path, output_dir, audience, hook)
    console.print("[bold green]Phase 0 complete.[/bold green] Inspect .agentic-readme/story.yaml and facts.json before producing.")


@app.command()
def produce(
    dir_path: Path = typer.Argument(Path("."), help="Project directory (contracts in .agentic-readme/)"),
):
    """Phase 1: Produce all media assets and README.md from locked story and facts."""
    story, facts = pipeline.load_contracts(dir_path)
    if story is None or facts is None:
        console.print("[red]Error: story.yaml or facts.json missing. Run 'ground' first.[/red]")
        raise typer.Exit(code=1)
    pipeline.produce(story, facts, dir_path)
    console.print("[bold green]Phase 1 complete.[/bold green] Assets generated in assets/ and README.md.")


@app.command()
def verify(
    dir_path: Path = typer.Argument(Path("."), help="Project directory containing README.md and .agentic-readme/facts.json"),
):
    """Phase 2: Audit claims, check GitHub rendering rules, and clean voice."""
    _story, facts = pipeline.load_contracts(dir_path)
    if facts is None:
        console.print("[red]Error: facts.json missing. Cannot audit claims without ground truth.[/red]")
        raise typer.Exit(code=1)
    report, passed = pipeline.verify(dir_path, facts)
    _show(report)
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
    report = pipeline.check(readme_path, FactsLedger.load(facts_file))
    _show(report)
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def run(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository"),
    output_dir: Path | None = typer.Option(None, "--output", "-o", help="Output directory"),
    review: bool = typer.Option(False, "--review", help="Pause after grounding so you can edit story.yaml"),
):
    """Run full 3-phase pipeline (Ground -> Produce -> Verify)."""
    if not review:
        result = pipeline.run(repo_path, output_dir)
        _show(result["report"])
        if not result["passed"]:
            raise typer.Exit(code=1)
        return

    out = output_dir or repo_path
    pipeline.ground(repo_path, out)
    console.print("[bold yellow]⏸ Review gate:[/bold yellow] edit .agentic-readme/story.yaml now if you want to.")
    if not typer.confirm("Continue to produce and verify?"):
        raise typer.Exit(code=1)
    story, facts = pipeline.load_contracts(out)  # re-read, so your edits are used
    pipeline.produce(story, facts, out)
    report, passed = pipeline.verify(out, facts)
    _show(report)
    if not passed:
        raise typer.Exit(code=1)


@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) stdio server for Claude, GPT, and Cursor."""
    from agentic_readme.mcp import run_mcp_server
    run_mcp_server()


def _show(report: VerificationReport) -> None:
    """Print the findings as a table, then a one-line summary."""
    table = Table(title="Phase 2 Verification Report")
    table.add_column("Category", style="cyan")
    table.add_column("Severity", style="magenta")
    table.add_column("Finding / Drift", style="yellow")
    table.add_column("Location", style="white")

    for f in report.findings:
        color = "red" if f.severity == FindingSeverity.FATAL else "yellow"
        table.add_row(f.category.value, f"[{color}]{f.severity.value}[/{color}]", f.message, f.location or "—")

    console.print(table)
    console.print(f"Summary: [bold]{report.facts_checked}[/bold] facts checked. "
                  f"[bold red]{report.fatal_count} fatal errors[/bold red], "
                  f"[bold yellow]{report.warning_count} warnings[/bold yellow].")


if __name__ == "__main__":
    app()
