"""The whole deterministic pipeline on one page.

    ground  : read the repo           -> .agentic-readme/facts.json + story.yaml
    produce : read those two files    -> README.md + assets/ (diagram, demo, video storyboard)
    check   : compare README + assets against facts.json (read-only)
    verify  : check, auto-fix what has one right answer, check again
    run     : ground -> produce -> verify

Same repo in, same files out: there is no LLM in this file. The agent (agent/graph.py)
calls these functions as tools. It can rewrite the words in story.yaml, but every number
comes from facts.json, and verify fails the run if one drifts.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from agentic_readme.ground.facts import collect_facts
from agentic_readme.ground.project import detect_project
from agentic_readme.ground.story import build_story, refresh_story
from agentic_readme.models import FactsLedger, FindingCategory, FindingSeverity, StorySpec, VerificationReport
from agentic_readme.produce.demo import make_demo
from agentic_readme.produce.diagram import draw_diagrams
from agentic_readme.produce.readme import write_readme
from agentic_readme.produce.video import make_storyboard
from agentic_readme.verify.claims import check_claims
from agentic_readme.verify.fixer import auto_fix
from agentic_readme.verify.rendering import check_rendering
from agentic_readme.verify.voice import check_voice

CONTRACTS_DIR = ".agentic-readme"

# Progress goes to stderr, so stdout stays clean for reports (and for the MCP protocol).
console = Console(stderr=True)


def contract_path(root: Path, name: str) -> Path:
    """Where story.yaml / facts.json live: root/.agentic-readme/<name>.

    Repos grounded before that folder existed keep theirs at the root; that copy is used
    until a new one is written.
    """
    new = Path(root) / CONTRACTS_DIR / name
    legacy = Path(root) / name
    return legacy if legacy.exists() and not new.exists() else new


def load_contracts(project_dir: Path) -> tuple[StorySpec | None, FactsLedger | None]:
    """Read story.yaml and facts.json. Either is None if its file doesn't exist."""
    story_file = contract_path(project_dir, "story.yaml")
    facts_file = contract_path(project_dir, "facts.json")
    story = StorySpec.load(story_file) if story_file.exists() else None
    facts = FactsLedger.load(facts_file) if facts_file.exists() else None
    return story, facts


def ground(
    repo_path: Path,
    output_dir: Path | None = None,
    audience: str | None = None,
    hook: str | None = None,
) -> tuple[StorySpec, FactsLedger]:
    """Step 1: inspect the repo and write facts.json + story.yaml."""
    repo = Path(repo_path).resolve()
    out = Path(output_dir or repo).resolve()
    console.print(f"[bold cyan][Phase 0: GROUND][/bold cyan] Analyzing repository at {repo}...")

    project = detect_project(repo)
    facts = collect_facts(repo, project.entrypoints)

    existing = contract_path(out, "story.yaml")
    if existing.exists():
        # Someone may have edited the story: keep their words, refresh only the numbers.
        story = refresh_story(StorySpec.load(existing), facts, audience, hook)
        console.print(f"[green]✔ Kept your edits to {existing.name}[/green] (numbers refreshed from facts)")
    else:
        story = build_story(project, facts, audience, hook)

    story_file = out / CONTRACTS_DIR / "story.yaml"
    facts_file = out / CONTRACTS_DIR / "facts.json"
    story.save(story_file)
    facts.save(facts_file)

    console.print("[green]✔ Locked contracts created:[/green]")
    console.print(f"  - Story Spec: [bold]{story_file}[/bold]")
    console.print(f"  - Facts Ledger: [bold]{facts_file}[/bold] ({len(facts.facts)} facts recorded)")
    return story, facts


def produce(story: StorySpec, facts: FactsLedger, output_dir: Path) -> dict:
    """Step 2: build every asset from the two contract files, and nothing else."""
    out = Path(output_dir).resolve()
    console.print("[bold cyan][Phase 1: PRODUCE][/bold cyan] Generating assets from locked story & facts...")

    diagrams = draw_diagrams(story, out)
    console.print("  [green]✔ Diagrams:[/green] .excalidraw + light, dark and static SVGs")
    demo = make_demo(story, out)
    console.print("  [green]✔ Demo:[/green] VHS script + illustrated terminal preview")
    video = make_storyboard(story, facts, out)
    console.print("  [green]✔ Video storyboard:[/green] /brag 20s spec + scene table")
    readme = write_readme(story, facts, out)
    console.print("  [green]✔ README:[/green] candidate README.md")

    return {"diagrams": diagrams, "demo": demo, "video": video, "readme": readme}


def check(readme_path: Path, facts: FactsLedger) -> VerificationReport:
    """Run all three checkers once. Read-only, so it's safe as a CI gate."""
    report = VerificationReport()
    check_claims(readme_path, facts, report)
    check_rendering(readme_path, report)
    check_voice(readme_path, report)
    return report


def verify(project_dir: Path, facts: FactsLedger, max_rounds: int = 2) -> tuple[VerificationReport, bool]:
    """Step 3: check -> auto-fix -> check again (an evaluator-optimizer loop with no LLM).

    Passes when no fatal findings remain.
    """
    project_dir = Path(project_dir).resolve()
    console.print("[bold cyan][Phase 2: VERIFY][/bold cyan] Running cross-asset verification & claim auditing...")

    readme = project_dir / "README.md"
    if not readme.exists():
        report = VerificationReport(passed=False)
        report.add_finding(
            FindingCategory.RENDER_ISSUE, FindingSeverity.FATAL,
            f"Target README.md does not exist at {readme}. Generate README first or run produce.",
            location=str(readme), expected="Existing README.md", actual="File not found",
            suggested_fix="Run 'agentic-readme produce' or 'agentic-readme run' to generate README.md.",
        )
        return report, False

    for round_number in range(1, max_rounds + 1):
        report = check(readme, facts)
        clean = report.fatal_count == 0 and report.warning_count == 0
        if clean or round_number == max_rounds:
            break
        auto_fix(readme, facts, report)

    passed = report.fatal_count == 0
    if passed:
        console.print(f"[green]✔ Verification PASSED[/green] ({report.facts_checked} facts checked, 0 fatal bugs)")
    else:
        console.print(f"[yellow]⚠ Verification finished with {report.fatal_count} fatal findings[/yellow]")
    return report, passed


def run(repo_path: Path, output_dir: Path | None = None, auto_approve: bool = True) -> dict:
    """ground -> produce -> verify, in one call."""
    out = Path(output_dir or repo_path).resolve()
    story, facts = ground(repo_path, out)
    if not auto_approve:
        console.print("[bold yellow]⏸ HUMAN GATE: Please inspect .agentic-readme/story.yaml and facts.json before continuing.[/bold yellow]")
    assets = produce(story, facts, out)
    report, passed = verify(out, facts)
    return {"story": story, "facts": facts, "assets": assets, "report": report, "passed": passed}
