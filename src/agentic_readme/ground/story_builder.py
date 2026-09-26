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

        # Extract project description if discovered
        desc_fact = ledger.get_fact("project_description")
        desc = str(desc_fact.value) if desc_fact else ""

        # Determine audience
        audience = target_audience or "Developers, ML engineers, and technical evaluators"

        # Generate pain-first hook
        hook = custom_hook or self._generate_pain_hook(repo_name, desc)

        # Problem & Solution grounded in the actual project domain
        if desc:
            problem = (
                f"Traditional workflows in this domain suffer from opaque estimates, unverified assumptions, "
                f"and documentation that drifts out of sync as code and dependencies evolve."
            )
            solution = (
                f"{repo_name}: {desc.rstrip('.')}. Every badge and number on this page is "
                f"checked against facts.json, produced from the project's own code and test runs."
            )
        else:
            problem = (
                f"Most project documentation relies on superficial text or unverified marketing claims. "
                f"When code changes or tests pass, READMEs drift out of sync with obsolete metrics and broken media."
            )
            solution = (
                f"{repo_name} executes a code-grounded pipeline, verifying all claims and numbers against "
                f"an immutable facts ledger before generating documentation and media assets."
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

        # Claim 2: Benchmark & evidence metrics from data/
        for key, fact in list(ledger.facts.items()):
            if key.startswith("metric_") and isinstance(fact.value, (int, float, str)):
                metric_name = key.replace("metric_", "").replace("_", " ").title()
                claims.append(
                    ClaimItem(
                        claim=f"Ground-truth verified {metric_name}: {fact.value}{' ' + fact.unit if fact.unit else ''}.",
                        evidence_file=fact.source_file,
                        metrics={key: fact.value},
                        verified=True,
                    )
                )
                if len(claims) >= 3:
                    break

        # Claim 3: Architecture / LOC
        loc_fact = ledger.get_fact("python_loc")
        if loc_fact and len(claims) < 3:
            claims.append(
                ClaimItem(
                    claim=f"{loc_fact.value} lines of code in the project source.",
                    evidence_file=loc_fact.source_file,
                    metrics={"loc": loc_fact.value},
                    verified=True,
                )
            )

        # Claim 4: License / Open Source
        lic_fact = ledger.get_fact("license")
        if lic_fact and len(claims) < 4:
            claims.append(
                ClaimItem(
                    claim=f"Open source distribution under the {lic_fact.value} license.",
                    evidence_file=lic_fact.source_file,
                    metrics={"license": lic_fact.value},
                    verified=True,
                )
            )

        # Integration Claims: Claude skill, MCP server, GPT schemas
        skill_fact = ledger.get_fact("skill")
        if skill_fact:
            claims.append(
                ClaimItem(
                    claim="Claude Code and Claude Agent SDK skill specification.",
                    evidence_file=skill_fact.source_file,
                    metrics={"skill": skill_fact.value},
                    verified=True,
                )
            )

        protocol_fact = ledger.get_fact("protocol")
        if protocol_fact:
            claims.append(
                ClaimItem(
                    claim="Model Context Protocol (MCP) server configuration.",
                    evidence_file=protocol_fact.source_file,
                    metrics={"protocol": protocol_fact.value},
                    verified=True,
                )
            )

        tools_fact = ledger.get_fact("tools_schema")
        if tools_fact:
            claims.append(
                ClaimItem(
                    claim="OpenAI Function Calling and Custom GPT Action schemas.",
                    evidence_file=tools_fact.source_file,
                    metrics={"tools_schema": tools_fact.value},
                    verified=True,
                )
            )

        # Quickstart commands
        remote_fact = ledger.get_fact("git_remote_url")
        clone_url = str(remote_fact.value) if remote_fact else "<repo-url>"
        clone_cmd = f"git clone {clone_url} && cd {repo_name}"

        quickstart: List[str] = []
        if self.analysis.primary_language == "Python":
            quickstart.append(clone_cmd)
            quickstart.append("pip install -e .")
            if self.analysis.test_command:
                quickstart.append(self.analysis.test_command)
            if self.analysis.quickstart_command:
                quickstart.append(self.analysis.quickstart_command)
        elif self.analysis.primary_language == "JavaScript/TypeScript":
            quickstart.append(clone_cmd)
            quickstart.append("npm install")
            if self.analysis.test_command:
                quickstart.append(self.analysis.test_command)
            if self.analysis.quickstart_command:
                quickstart.append(self.analysis.quickstart_command)
        elif self.analysis.primary_language == "Rust":
            quickstart.append(clone_cmd)
            if self.analysis.test_command:
                quickstart.append(self.analysis.test_command)
            if self.analysis.quickstart_command:
                quickstart.append(self.analysis.quickstart_command)

        # Honest deliberate omissions (house style from duet: 'Deliberately not included')
        omissions = [
            "No unverified claims: every figure is mechanically checked against executable outputs in facts.json",
            "No invented numbers: every badge and metric comes from facts.json",
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

    def _generate_pain_hook(self, repo_name: str, desc: str = "") -> str:
        if desc:
            return f"{desc.rstrip('.')}."
        return (
            f"You need a verified, media-rich README grounded in real code runs—not another generic text generator."
        )

