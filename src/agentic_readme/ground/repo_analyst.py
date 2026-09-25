"""Repo Analyst for Phase 0 Grounding.

Inspects code, executes safe verification commands (e.g., pytest, CLI help),
discovers entry points and architecture stages, and provides structural context.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from agentic_readme.core.models import ArchitectureNode, FactsLedger
from agentic_readme.ground.facts_extractor import FactsExtractor


class RepoAnalysis:
    """Consolidated repo inspection result."""
    def __init__(
        self,
        repo_name: str,
        repo_path: Path,
        primary_language: str,
        entrypoints: List[str],
        test_command: Optional[str],
        quickstart_command: Optional[str],
        architecture_nodes: List[ArchitectureNode],
        facts_ledger: FactsLedger,
    ):
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.primary_language = primary_language
        self.entrypoints = entrypoints
        self.test_command = test_command
        self.quickstart_command = quickstart_command
        self.architecture_nodes = architecture_nodes
        self.facts_ledger = facts_ledger


class RepoAnalyst:
    """Agent in Phase 0 responsible for inspecting and running the codebase."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

    def analyze(self) -> RepoAnalysis:
        repo_name = self.repo_path.name

        # 1. Extract ground truth facts
        extractor = FactsExtractor(self.repo_path)
        ledger = extractor.extract_all(repo_name=repo_name)

        # 2. Detect language and entry points
        lang, entrypoints = self._detect_stack_and_entrypoints()

        # 3. Detect run & test commands
        test_cmd, quickstart_cmd = self._detect_commands(lang, entrypoints)

        # 4. Synthesize code-grounded architecture nodes
        arch_nodes = self._derive_architecture_nodes(entrypoints)

        return RepoAnalysis(
            repo_name=repo_name,
            repo_path=self.repo_path,
            primary_language=lang,
            entrypoints=entrypoints,
            test_command=test_cmd,
            quickstart_command=quickstart_cmd,
            architecture_nodes=arch_nodes,
            facts_ledger=ledger,
        )

    def _detect_stack_and_entrypoints(self) -> tuple[str, List[str]]:
        entrypoints: List[str] = []
        lang = "Unknown"

        # Check Python
        pyproject = self.repo_path / "pyproject.toml"
        setup_py = self.repo_path / "setup.py"
        py_files = list(self.repo_path.glob("*.py")) + list(self.repo_path.glob("src/**/*.py"))

        if pyproject.exists() or setup_py.exists() or py_files:
            lang = "Python"
            candidates = ["main.py", "app.py", "cli.py", "run.py", "src/agentic_readme/cli.py"]
            for cand in candidates:
                if (self.repo_path / cand).exists():
                    entrypoints.append(cand)
            if not entrypoints and py_files:
                entrypoints.append(str(py_files[0].relative_to(self.repo_path)))
            return lang, entrypoints

        # Check Node / TS
        if (self.repo_path / "package.json").exists():
            lang = "JavaScript/TypeScript"
            for cand in ["index.js", "src/index.ts", "main.js", "app.js"]:
                if (self.repo_path / cand).exists():
                    entrypoints.append(cand)
            return lang, entrypoints

        # Check Rust
        if (self.repo_path / "Cargo.toml").exists():
            lang = "Rust"
            for cand in ["src/main.rs", "src/lib.rs"]:
                if (self.repo_path / cand).exists():
                    entrypoints.append(cand)
            return lang, entrypoints

        # Check Shell
        sh_files = list(self.repo_path.glob("*.sh"))
        if sh_files:
            lang = "Bash"
            entrypoints.extend([str(f.relative_to(self.repo_path)) for f in sh_files])
            return lang, entrypoints

        return lang, entrypoints

    def _detect_commands(self, lang: str, entrypoints: List[str]) -> tuple[Optional[str], Optional[str]]:
        test_cmd = None
        quickstart_cmd = None

        if lang == "Python":
            if (self.repo_path / "tests").exists() or (self.repo_path / "test").exists():
                test_cmd = "pytest"
            if entrypoints:
                ep = entrypoints[0]
                quickstart_cmd = f"python3 {ep}"
        elif lang == "JavaScript/TypeScript":
            test_cmd = "npm test"
            quickstart_cmd = "npm start"
        elif lang == "Rust":
            test_cmd = "cargo test"
            quickstart_cmd = "cargo run"
        elif lang == "Bash" and entrypoints:
            test_cmd = None
            quickstart_cmd = f"./{entrypoints[0]}"

        return test_cmd, quickstart_cmd

    def _derive_architecture_nodes(self, entrypoints: List[str]) -> List[ArchitectureNode]:
        """Derive functional stages from existing directories and files."""
        nodes: List[ArchitectureNode] = []

        if entrypoints:
            nodes.append(
                ArchitectureNode(
                    id="entrypoint",
                    label=f"CLI / Entrypoint ({Path(entrypoints[0]).name})",
                    role="entrypoint",
                    source_file=entrypoints[0],
                )
            )

        # Check for core or processor directories
        stage_dirs = [
            ("ground", "Grounding Engine", "pipeline_stage"),
            ("produce", "Asset Producers", "pipeline_stage"),
            ("verify", "Claim Auditor & Verifiers", "guardrail"),
            ("models", "Inference & CV Models", "pipeline_stage"),
            ("data", "Pricing & Ground Truth Data", "storage"),
            ("api", "Service API Layer", "entrypoint"),
        ]

        for dirname, label, role in stage_dirs:
            if (self.repo_path / dirname).exists() or (self.repo_path / "src" / dirname).exists():
                nodes.append(
                    ArchitectureNode(
                        id=dirname,
                        label=label,
                        role=role,
                        source_file=dirname,
                    )
                )

        if not nodes:
            nodes = [
                ArchitectureNode(id="core", label="Core Processing Pipeline", role="pipeline_stage"),
                ArchitectureNode(id="output", label="Verified Output Artifacts", role="output"),
            ]

        return nodes
