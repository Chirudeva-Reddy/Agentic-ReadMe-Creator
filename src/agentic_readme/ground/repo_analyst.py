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

        # 4. Safe execution test: try running CLI help if available
        self._test_headless_run(entrypoints, ledger)

        # 5. Synthesize code-grounded architecture nodes
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

    def _test_headless_run(self, entrypoints: List[str], ledger: FactsLedger) -> None:
        """Attempt safe verification run (CLI --help) to capture real outputs."""
        if not entrypoints:
            ledger.add_fact(
                key="headless_run_status",
                value="no_entrypoint_found",
                source_file=".",
                description="Headless run status: no entrypoint found",
            )
            return

        ep = entrypoints[0]
        if ep.endswith(".py"):
            try:
                res = subprocess.run(
                    ["python3", ep, "--help"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if res.returncode == 0 and res.stdout.strip():
                    help_line = res.stdout.strip().splitlines()[0][:120]
                    ledger.add_fact(
                        key="cli_help_output",
                        value=help_line,
                        source_file=ep,
                        description="Verified CLI help output from live execution",
                    )
                    ledger.add_fact(
                        key="headless_run_status",
                        value="verified_headless",
                        source_file=ep,
                        description="Project successfully ran headless",
                    )
                    return
            except Exception:
                pass

        ledger.add_fact(
            key="headless_run_status",
            value="fallback_static_only",
            source_file=ep,
            description="Headless run unverified; using static replay/diagram fallback",
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

        # Neutral labels only: the directory name is all we know, so don't imply a domain
        known_roles = {
            "ground": ("Grounding Engine", "pipeline_stage"),
            "produce": ("Asset Producers", "pipeline_stage"),
            "verify": ("Claim Auditor & Verifiers", "guardrail"),
            "models": ("Models", "pipeline_stage"),
            "triage": ("Triage Logic", "pipeline_stage"),
            "data": ("Data Files", "storage"),
            "api": ("Service API Layer", "entrypoint"),
            "core": ("Core Processing Engine", "pipeline_stage"),
            "services": ("Business Services", "pipeline_stage"),
            "agents": ("Multi-Agent Subsystems", "pipeline_stage"),
        }

        # Check top-level and src/ subdirectories
        candidates = []
        for p in self.repo_path.iterdir():
            if (
                p.is_dir()
                and not p.name.startswith(".")
                and not p.name.endswith(".egg-info")
                and p.name not in ("tests", "test", "venv", ".venv", "docs", "assets", "dist", "build", "__pycache__")
            ):
                candidates.append(p)
        src_dir = self.repo_path / "src"
        if src_dir.exists() and src_dir.is_dir():
            for p in src_dir.iterdir():
                if (
                    p.is_dir()
                    and not p.name.startswith(".")
                    and not p.name.endswith(".egg-info")
                    and p.name not in ("tests", "test", "docs", "dist", "build", "__pycache__")
                ):
                    candidates.append(p)

        seen_ids = set()
        for cand in candidates:
            cname = cand.name.lower()
            if cname in known_roles:
                label, role = known_roles[cname]
                node_id = cname
            else:
                label = f"{cand.name.replace('_', ' ').title()} Module"
                role = "pipeline_stage"
                node_id = cand.name

            if node_id not in seen_ids:
                seen_ids.add(node_id)
                nodes.append(
                    ArchitectureNode(
                        id=node_id,
                        label=label,
                        role=role,
                        source_file=str(cand.relative_to(self.repo_path)),
                    )
                )

        if not nodes:
            nodes = [
                ArchitectureNode(id="core", label="Core Processing Pipeline", role="pipeline_stage"),
                ArchitectureNode(id="output", label="Verified Output Artifacts", role="output"),
            ]

        return nodes

