"""Write the first draft of story.yaml, or refresh the numbers in an edited one.

build_story(project, facts)   -> a new StorySpec: hook, problem, solution, claims, quickstart
refresh_story(story, facts)   -> the same story with its numbers updated from new facts

Every claim is built from a fact, so it carries the fact's value and evidence file.
The wording here is a plain first draft; the agent (or a human) rewrites the hook,
problem and solution in story.yaml, but never the numbers.
"""

from __future__ import annotations

import re

from agentic_readme.ground.project import Project
from agentic_readme.models import ClaimItem, FactItem, FactsLedger, StorySpec

# Claim metrics shown under a shorter name than their facts.json key.
METRIC_FACT_KEYS = {"loc": "python_loc"}

# The install step for each language (None: no separate install step).
INSTALL_STEP = {
    "Python": "pip install -e .",
    "JavaScript/TypeScript": "npm install",
    "Rust": None,
}

DEFAULT_AUDIENCE = "Developers, ML engineers, and technical evaluators"

DELIBERATE_OMISSIONS = [
    "No unverified claims: every figure is mechanically checked against executable outputs in facts.json",
    "No invented numbers: every badge and metric comes from facts.json",
    "No relative <video> tags in README that fail to render on GitHub",
    "No marketing buzzwords or generic template greetings",
]


def build_story(
    project: Project,
    facts: FactsLedger,
    audience: str | None = None,
    hook: str | None = None,
) -> StorySpec:
    name = project.name
    description_fact = facts.get_fact("project_description")
    description = str(description_fact.value) if description_fact else ""

    if description:
        default_hook = f"{description.rstrip('.')}."
        problem = (
            "Traditional workflows in this domain suffer from opaque estimates, unverified assumptions, "
            "and documentation that drifts out of sync as code and dependencies evolve."
        )
        solution = f"{name}: {description.rstrip('.')}."
    else:
        default_hook = "You need a verified, media-rich README grounded in real code runs—not another generic text generator."
        problem = (
            "Most project documentation relies on superficial text or unverified marketing claims. "
            "When code changes or tests pass, READMEs drift out of sync with obsolete metrics and broken media."
        )
        solution = (
            f"{name} executes a code-grounded pipeline, verifying all claims and numbers against "
            f"an immutable facts ledger before generating documentation and media assets."
        )

    return StorySpec(
        repo_name=name,
        target_audience=audience or DEFAULT_AUDIENCE,
        hook=hook or default_hook,
        problem=problem,
        solution=solution,
        key_claims=_claims(facts),
        architecture_nodes=project.architecture_nodes,
        quickstart_commands=_quickstart(project, facts),
        deliberate_omissions=DELIBERATE_OMISSIONS,
        evidence_summary="Every figure above is verified against source code and execution logs in facts.json",
    )


def _claim(text: str, fact: FactItem, metric_name: str) -> ClaimItem:
    """A claim that cites one fact."""
    return ClaimItem(claim=text, evidence_file=fact.source_file, metrics={metric_name: fact.value}, verified=True)


def _claims(facts: FactsLedger) -> list[ClaimItem]:
    """Up to three headline claims (tests, benchmark numbers, size), then license and integrations."""
    claims: list[ClaimItem] = []

    tests = facts.get_fact("test_count")
    if tests:
        claims.append(_claim(f"Automated test suite with {tests.value} passing tests verifying core system invariants.",
                             tests, "test_count"))

    for key, fact in facts.facts.items():
        if key.startswith("metric_") and isinstance(fact.value, (int, float, str)):
            name = key.replace("metric_", "").replace("_", " ").title()
            unit = f" {fact.unit}" if fact.unit else ""
            claims.append(_claim(f"Ground-truth verified {name}: {fact.value}{unit}.", fact, key))
            if len(claims) >= 3:
                break

    loc = facts.get_fact("python_loc")
    if loc and len(claims) < 3:
        claims.append(_claim(f"{loc.value} lines of code in the project source.", loc, "loc"))

    license_fact = facts.get_fact("license")
    if license_fact and len(claims) < 4:
        claims.append(_claim(f"Open source distribution under the {license_fact.value} license.", license_fact, "license"))

    integrations = [
        ("skill", "Claude Code and Claude Agent SDK skill specification."),
        ("protocol", "Model Context Protocol (MCP) server configuration."),
        ("tools_schema", "OpenAI Function Calling and Custom GPT Action schemas."),
    ]
    for key, text in integrations:
        fact = facts.get_fact(key)
        if fact:
            claims.append(_claim(text, fact, key))

    return claims


def _quickstart(project: Project, facts: FactsLedger) -> list[str]:
    """clone -> install -> test -> run, for the languages we know how to install."""
    if project.language not in INSTALL_STEP:
        return []
    remote = facts.get_fact("git_remote_url")
    clone_url = str(remote.value) if remote else "<repo-url>"

    commands = [f"git clone {clone_url} && cd {project.name}"]
    if INSTALL_STEP[project.language]:
        commands.append(INSTALL_STEP[project.language])
    if project.test_command:
        commands.append(project.test_command)
    if project.run_command:
        commands.append(project.run_command)
    return commands


def refresh_story(
    existing: StorySpec,
    facts: FactsLedger,
    audience: str | None = None,
    hook: str | None = None,
) -> StorySpec:
    """Re-ground an edited story: keep every human-written field, update only the numbers.

    Each claim's metrics are reset to the ledger's current values, and the old value is
    swapped for the new one in the claim text. Claims the user deleted stay deleted.
    """
    claims = []
    for item in existing.key_claims:
        text, metrics = item.claim, dict(item.metrics)
        for key, old in item.metrics.items():
            fact = facts.get_fact(METRIC_FACT_KEYS.get(key, key))
            if fact is None or fact.value == old:
                continue
            # ponytail: whole-token swap only, so 48 -> 53 leaves 480 and 4.8 alone
            text = re.sub(rf"(?<![\w.]){re.escape(str(old))}(?!\w|\.\d)", str(fact.value), text)
            metrics[key] = fact.value
        claims.append(item.model_copy(update={"claim": text, "metrics": metrics}))

    return existing.model_copy(update={
        "key_claims": claims,
        "hook": hook or existing.hook,
        "target_audience": audience or existing.target_audience,
    })
