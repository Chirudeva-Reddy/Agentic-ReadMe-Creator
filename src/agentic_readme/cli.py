"""The `agentic-readme` command: the front door for humans and CI.

Each command is a thin wrapper around one function in pipeline.py:

    ground   -> pipeline.ground     write facts.json + story.yaml
    produce  -> pipeline.produce    write README.md + assets/
    verify   -> pipeline.verify     check, auto-fix, check again; exit 1 on fatal findings
    audit    -> pipeline.check      read-only check of any README; exit 1 on fatal findings
    run      -> pipeline.run        all three steps
    agent    -> agent.graph         an LLM improves the story, using the steps above as tools
    eval     -> agent.evaluate      score the agent on examples/ in LangSmith
    mcp      -> mcp.run_mcp_server  the same tools for AI assistants (JSON-RPC over stdio)

The agent and eval imports live inside their commands, so the other commands (and CI)
start fast and never need an API key.

Typer turns each decorated function into a sub-command and its arguments into options.
"""

from __future__ import annotations

from pathlib import Path

import os

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
def agent(
    repo_path: Path = typer.Argument(Path("."), help="Path to repository"),
    model: str | None = typer.Option(None, "--model", "-m", help="provider:model (default: $AGENTIC_README_MODEL or anthropic:claude-opus-5-5)"),
    review: bool = typer.Option(False, "--review", help="Pause before the README is written so you can approve the story"),
    max_checks: int = typer.Option(3, "--max-checks", help="How many times the final check may send the agent back"),
):
    """Let the LLM agent write and verify the README, using the pipeline as its tools."""
    from agentic_readme.agent.graph import DEFAULT_MODEL, describe_step, run_agent

    model = model or os.environ.get("AGENTIC_README_MODEL", DEFAULT_MODEL)
    if model.startswith("anthropic:") and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error: set ANTHROPIC_API_KEY to run the agent.[/red] "
                      "`agentic-readme run` does the same job without an LLM.")
        raise typer.Exit(code=1)
    console.print(f"Agent: {model}. {_tracing_status()}")

    def ask_human(question: dict) -> str:
        console.print(question["story"], markup=False)
        return typer.prompt(question["question"])

    def print_step(update: dict) -> None:
        for line in describe_step(update):
            console.print(line, markup=False)

    result = run_agent(repo_path, model, review, max_checks, ask_human=ask_human, on_step=print_step)
    verdict = "[green]PASSED[/green]" if result["passed"] else "[red]FAILED[/red]"
    console.print(f"Agent finished: {verdict} after {len(result['tool_calls'])} tool calls and {result['checks']} final check(s).")
    if not result["passed"]:
        raise typer.Exit(code=1)


@app.command(name="eval")
def evaluate(
    examples_dir: Path = typer.Option(Path("examples"), "--examples", help="Folder of example projects"),
    model: str | None = typer.Option(None, "--model", "-m", help="provider:model to evaluate"),
):
    """Score the agent on every example project, as a LangSmith experiment."""
    if not os.environ.get("LANGSMITH_API_KEY"):
        console.print("[red]Error: set LANGSMITH_API_KEY to record the experiment in LangSmith.[/red]")
        raise typer.Exit(code=1)
    from agentic_readme.agent.evaluate import run_eval

    os.environ.setdefault("LANGSMITH_PROJECT", "agentic-readme")
    result = run_eval(examples_dir, model)
    console.print(f"Experiment [bold]{result['experiment']}[/bold] recorded: {result['url']}")


def _tracing_status() -> str:
    if os.environ.get("LANGSMITH_TRACING", "").lower() == "true" and os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_PROJECT", "agentic-readme")
        return f"LangSmith tracing on (project: {os.environ['LANGSMITH_PROJECT']})."
    return "LangSmith tracing off (set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to trace every step)."


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
