"""Builds the draft StorySpec narrative contract from Phase 0 RepoAnalysis.

Locks down the story, key claims, architecture, and facts before Phase 1 fan-out.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from agentic_readme.core.models import (
    ArchitectureNode,
    ClaimItem,
    FactsLedger,
    StorySpec,
)
from agentic_readme.ground.repo_analyst import RepoAnalysis


class StoryBuilder:
    """Builds and locks the StorySpec from RepoAnalysis."""

    def __init__(self, analysis: RepoAnalysis):
        self.analysis = analysis

    def build_story(
        self,
        target_audience: Optional[str] = None,
        custom_hook: Optional[str] = None,
    ) -> StorySpec:
        repo_name = self.analysis.repo_name
        ledger = self.analysis.facts_ledger

        # Determine audience
        audience = target_audience or "Developers, ML engineers, and technical evaluators"

        # Generate pain-first hook
        hook = custom_hook or self._generate_pain_hook(repo_name)

        # Problem & Solution
        problem = (
            f"Most documentation pipelines generate superficial text or unverified marketing claims. "
            f"When code changes or tests pass, READMEs drift out of sync, displaying obsolete counts and broken media."
        )
        solution = (
            f"{repo_name} binds documentation directly to code execution, verifying claims against "
            f"a deterministic facts ledger before generating code-grounded diagrams, demos, and READMEs."
        )

        # Build grounded key claims
        claims: List[ClaimItem] = []

        # Claim 1: Test verification
        test_fact = ledger.get_fact("test_count")
        if test_fact:
            claims.append(
                ClaimItem(
                    claim=f"Automated test suite with {test_fact.value} passing tests verifying core system invariants.",
                    evidence_file=test_fact.source_file,
                    metrics={"test_count": test_fact.value},
                    verified=True,
                )
            )

        # Claim 2: Architecture / LOC
        loc_fact = ledger.get_fact("python_loc")
        if loc_fact:
            claims.append(
                ClaimItem(
                    claim=f"Modular architecture spanning {loc_fact.value} lines of code across pipeline stages.",
                    evidence_file=loc_fact.source_file,
                    metrics={"loc": loc_fact.value},
                    verified=True,
                )
            )

        # Claim 3: License / Open Source
        lic_fact = ledger.get_fact("license")
        if lic_fact:
            claims.append(
                ClaimItem(
                    claim=f"Open source distribution under the {lic_fact.value} license.",
                    evidence_file=lic_fact.source_file,
                    metrics={"license": lic_fact.value},
                    verified=True,
                )
            )

        # Quickstart commands
        quickstart: List[str] = []
        if self.analysis.primary_language == "Python":
            quickstart.append("git clone <repo-url> && cd " + repo_name)
            quickstart.append("pip install -e .")
            if self.analysis.test_command:
                quickstart.append(self.analysis.test_command)
            if self.analysis.quickstart_command:
                quickstart.append(self.analysis.quickstart_command)

        # Honest deliberate omissions (house style from duet: 'Deliberately not included')
        omissions = [
            "No unverified LLM generation passes without ledger grounding",
            "No relative <video> tags in README that fail to render on GitHub",
            "No marketing buzzwords or generic template greetings",
        ]

        return StorySpec(
            repo_name=repo_name,
            target_audience=audience,
            hook=hook,
            problem=problem,
            solution=solution,
            key_claims=claims,
            architecture_nodes=self.analysis.architecture_nodes,
            quickstart_commands=quickstart,
            deliberate_omissions=omissions,
            evidence_summary="Every figure above is verified against source code and execution logs in facts.json",
        )

    def _generate_pain_hook(self, repo_name: str) -> str:
        return (
            f"You need a verified, media-rich README grounded in real code runs—not another generic text generator."
        )
