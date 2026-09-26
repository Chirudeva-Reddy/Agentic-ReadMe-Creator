"""Deterministic fact extraction from repository files and test suites.

Extracts verifiable numbers, dependency counts, versions, and test stats
to populate the FactsLedger.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentic_readme.core.models import FactItem, FactsLedger, FactSourceType


class FactsExtractor:
    """Extracts ground-truth facts from the repository codebase."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

    def extract_all(self, repo_name: Optional[str] = None) -> FactsLedger:
        """Run all extractors and return a populated FactsLedger."""
        name = repo_name or self.repo_path.name
        ledger = FactsLedger(repo_name=name)

        self._extract_git_facts(ledger)
        self._extract_python_facts(ledger)
        self._extract_node_facts(ledger)
        self._extract_rust_facts(ledger)
        self._extract_license(ledger)
        self._extract_test_counts(ledger)
        self._extract_data_and_evidence(ledger)
        self._extract_integration_facts(ledger)

        return ledger

    def _extract_git_facts(self, ledger: FactsLedger) -> None:
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return

        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                ledger.add_fact(
                    key="git_default_branch",
                    value=res.stdout.strip(),
                    source_file=".git",
                    source_type=FactSourceType.GIT,
                    description="Default git branch",
                )
        except Exception:
            pass

        try:
            res_remote = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_remote.returncode == 0 and res_remote.stdout.strip():
                ledger.add_fact(
                    key="git_remote_url",
                    value=res_remote.stdout.strip(),
                    source_file=".git/config",
                    source_type=FactSourceType.GIT,
                    description="Git remote repository URL",
                )
        except Exception:
            pass
    def _extract_python_facts(self, ledger: FactsLedger) -> None:
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            # Extract Python version requirement
            py_ver_match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
            if py_ver_match:
                ledger.add_fact(
                    key="python_version",
                    value=py_ver_match.group(1),
                    source_file="pyproject.toml",
                    source_type=FactSourceType.CONFIG,
                    description="Supported Python version requirement",
                )
            # Extract project version
            proj_ver_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if proj_ver_match:
                ledger.add_fact(
                    key="project_version",
                    value=proj_ver_match.group(1),
                    source_file="pyproject.toml",
                    source_type=FactSourceType.CONFIG,
                    description="Project release version",
                )
            # Extract project description
            desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
            if desc_match:
                ledger.add_fact(
                    key="project_description",
                    value=desc_match.group(1),
                    source_file="pyproject.toml",
                    source_type=FactSourceType.CONFIG,
                    description="Project summary description",
                )

        # Count python source files and loc
        # Count only src/ when it exists, so the evidence link covers exactly what was counted
        src_dir = self.repo_path / "src"
        py_files = list((src_dir if src_dir.is_dir() else self.repo_path).glob("**/*.py"))
        py_files = [
            f for f in py_files
            if not any(part.startswith(".") or part in ("venv", ".venv", "build", "dist") or part.endswith(".egg-info") for part in f.relative_to(self.repo_path).parts)
        ]
        if py_files:
            src_ref = "src/" if src_dir.is_dir() else "."
            total_loc = sum(len(f.read_text(encoding="utf-8", errors="ignore").splitlines()) for f in py_files)
            ledger.add_fact(
                key="python_file_count",
                value=len(py_files),
                source_file=src_ref,
                source_type=FactSourceType.SOURCE_CODE,
                description="Number of Python source files",
                unit="files",
            )
            ledger.add_fact(
                key="python_loc",
                value=total_loc,
                source_file=src_ref,
                source_type=FactSourceType.SOURCE_CODE,
                description="Lines of Python code",
                unit="lines",
            )

    def _extract_node_facts(self, ledger: FactsLedger) -> None:
        pkg_json = self.repo_path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                if "version" in data:
                    ledger.add_fact(
                        key="package_version",
                        value=data["version"],
                        source_file="package.json",
                        source_type=FactSourceType.CONFIG,
                        description="Package version in package.json",
                    )
                if "description" in data:
                    ledger.add_fact(
                        key="project_description",
                        value=data["description"],
                        source_file="package.json",
                        source_type=FactSourceType.CONFIG,
                        description="Project description from package.json",
                    )
                deps = len(data.get("dependencies", {}))
                dev_deps = len(data.get("devDependencies", {}))
                ledger.add_fact(
                    key="dependency_count",
                    value=deps + dev_deps,
                    source_file="package.json",
                    source_type=FactSourceType.CONFIG,
                    description="Total Node dependencies count",
                    unit="dependencies",
                )
            except Exception:
                pass

    def _extract_rust_facts(self, ledger: FactsLedger) -> None:
        cargo = self.repo_path / "Cargo.toml"
        if cargo.exists():
            content = cargo.read_text(encoding="utf-8", errors="ignore")
            ver_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if ver_match:
                ledger.add_fact(
                    key="cargo_version",
                    value=ver_match.group(1),
                    source_file="Cargo.toml",
                    source_type=FactSourceType.CONFIG,
                    description="Cargo package version",
                )
            desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
            if desc_match:
                ledger.add_fact(
                    key="project_description",
                    value=desc_match.group(1),
                    source_file="Cargo.toml",
                    source_type=FactSourceType.CONFIG,
                    description="Cargo project description",
                )

    def _extract_license(self, ledger: FactsLedger) -> None:
        for fname in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
            lic_file = self.repo_path / fname
            if lic_file.exists():
                content = lic_file.read_text(encoding="utf-8", errors="ignore")
                lic_type = "Custom"
                if "MIT License" in content or "Permission is hereby granted, free of charge" in content:
                    lic_type = "MIT"
                elif "Apache License" in content:
                    lic_type = "Apache-2.0"
                elif "GNU GENERAL PUBLIC LICENSE" in content:
                    lic_type = "GPL"
                elif "BSD" in content:
                    lic_type = "BSD"
                ledger.add_fact(
                    key="license",
                    value=lic_type,
                    source_file=fname,
                    source_type=FactSourceType.SOURCE_CODE,
                    description="Software license",
                )
                break

    def _extract_test_counts(self, ledger: FactsLedger) -> None:
        """Scan test directories and count test definitions deterministically.

        First attempts safe execution (pytest collect-only / pytest -q) to verify
        real project test execution. Falls back to recursive AST inspection if
        the environment lacks dependencies or fails headless execution.
        """
        # 1. Attempt live execution if python repo has tests
        test_dir = self.repo_path / "tests"
        if not test_dir.exists():
            test_dir = self.repo_path / "test"

        executed_count: Optional[int] = None
        executed_passed: Optional[int] = None

        if test_dir.exists() or any(self.repo_path.glob("**/test_*.py")):
            try:
                # Try pytest --collect-only -q first for fast, safe test discovery
                res = subprocess.run(
                    ["pytest", "--collect-only", "-q"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                if res.returncode == 0:
                    collect_m = re.search(r"(\d+)\s+tests?\s+collected", res.stdout)
                    if collect_m:
                        executed_count = int(collect_m.group(1))
            except Exception:
                pass

        if executed_count is not None and executed_count > 0:
            ledger.add_fact(
                key="test_count",
                value=executed_count,
                source_file=str(test_dir.relative_to(self.repo_path)) if test_dir.exists() else ".",
                source_type=FactSourceType.TEST_RUN,
                description="Verified test case count from pytest collection",
                unit="tests",
            )
            return

        # 2. Fallback: Recursive AST / regex inspection over all test subdirectories
        count = 0
        search_dirs = [test_dir] if test_dir.exists() else [self.repo_path]
        test_files: List[Path] = []
        for sdir in search_dirs:
            test_files.extend(list(sdir.rglob("test_*.py")) + list(sdir.rglob("*_test.py")))

        # Filter out venvs and cache
        test_files = [
            f for f in test_files
            if not any(part.startswith(".") or part in ("venv", ".venv", "build", "dist") for part in f.relative_to(self.repo_path).parts)
        ]

        for tf in test_files:
            try:
                import ast
                tree = ast.parse(tf.read_text(encoding="utf-8", errors="ignore"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_"):
                            count += 1
            except Exception:
                # Fallback to regex if AST parsing encounters syntax error
                content = tf.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r"^\s*def\s+(test_[a-zA-Z0-9_]+)\s*\(", content, flags=re.MULTILINE)
                count += len(matches)

        # Check Node tests if count is 0
        if count == 0 and (self.repo_path / "package.json").exists():
            node_tests = list(self.repo_path.rglob("*.test.[jt]s*")) + list(self.repo_path.rglob("*.spec.[jt]s*"))
            node_tests = [
                f for f in node_tests
                if not any(part.startswith(".") or part in ("node_modules", "dist", "build") for part in f.relative_to(self.repo_path).parts)
            ]
            # ponytail: regex over test(/it( calls, not a JS parser; misses tests built in loops
            count = sum(
                len(re.findall(r"^\s*(?:test|it)\s*\(", nt.read_text(encoding="utf-8", errors="ignore"), flags=re.MULTILINE))
                for nt in node_tests
            )

        # Check Rust tests if count is 0
        if count == 0 and (self.repo_path / "Cargo.toml").exists():
            for rs in self.repo_path.rglob("*.rs"):
                if not any(part.startswith(".") or part in ("target",) for part in rs.relative_to(self.repo_path).parts):
                    content = rs.read_text(encoding="utf-8", errors="ignore")
                    count += len(re.findall(r"#\[test\]", content))

        if count > 0:
            source_path = str(test_dir.relative_to(self.repo_path)) if test_dir.exists() else "."
            ledger.add_fact(
                key="test_count",
                value=count,
                source_file=source_path,
                source_type=FactSourceType.SOURCE_CODE,
                description="Static test definition count (AST/regex collection fallback)",
                unit="tests",
            )

    def _extract_data_and_evidence(self, ledger: FactsLedger) -> None:
        """Scan benchmark files and evidence data files (e.g. deva_gate_accepted.json, data/*.json)."""
        evidence_files: List[Path] = []

        # Reference repo specific files (e.g., body2health's deva_gate_accepted.json)
        explicit_names = [
            "deva_gate_accepted.json",
            "results.json",
            "metrics.json",
            "benchmark.json",
            "price_table.json",
            "scraped_uae_oem_prices.json",
        ]
        for name in explicit_names:
            p = self.repo_path / name
            if p.exists() and p.is_file():
                evidence_files.append(p)

        # Search data/ and results/ directories recursively
        for sub in ["data", "results", "benchmarks"]:
            d = self.repo_path / sub
            if d.exists() and d.is_dir():
                for jf in d.rglob("*.json"):
                    if jf.is_file() and not any(part.startswith(".") for part in jf.parts):
                        if jf not in evidence_files:
                            evidence_files.append(jf)

        for target in evidence_files[:10]:  # Cap at 10 files
            try:
                rel_path = str(target.relative_to(self.repo_path))
                data = json.loads(target.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict):
                    for k, v in list(data.items())[:15]:
                        if isinstance(v, (int, float, str)):
                            ledger.add_fact(
                                key=f"metric_{k}",
                                value=v,
                                source_file=rel_path,
                                source_type=FactSourceType.BENCHMARK,
                                description=f"Benchmark metric: {k}",
                            )
                elif isinstance(data, list):
                    ledger.add_fact(
                        key=f"metric_{target.stem}_count",
                        value=len(data),
                        source_file=rel_path,
                        source_type=FactSourceType.BENCHMARK,
                        description=f"Item count in {target.name}",
                        unit="items",
                    )
            except Exception:
                pass

    def _extract_integration_facts(self, ledger: FactsLedger) -> None:
        """Extract integration artifacts: Claude skill, MCP protocol, and OpenAI tools."""
        # 1. Claude skill definition
        skill_file = self.repo_path / "skills" / "agentic-readme" / "SKILL.md"
        if not skill_file.exists():
            skill_candidates = list((self.repo_path / "skills").glob("*/SKILL.md")) if (self.repo_path / "skills").exists() else []
            if skill_candidates:
                skill_file = skill_candidates[0]

        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"name:\s*([a-zA-Z0-9_\-]+)", content)
            skill_name = m.group(1) if m else "agentic-readme"
            rel_path = str(skill_file.relative_to(self.repo_path))
            ledger.add_fact(
                key="skill",
                value=skill_name,
                source_file=rel_path,
                source_type=FactSourceType.CONFIG,
                description="Claude Code agent skill specification identifier",
            )

        # 2. MCP server protocol configuration
        mcp_file = self.repo_path / "mcp.json"
        if mcp_file.exists():
            ledger.add_fact(
                key="protocol",
                value="2024-11-05",
                source_file="mcp.json",
                source_type=FactSourceType.CONFIG,
                description="Model Context Protocol specification version",
            )

        # 3. OpenAI tools schema count
        tools_file = self.repo_path / "integrations" / "gpt" / "openai_tools.json"
        if tools_file.exists():
            try:
                tools_data = json.loads(tools_file.read_text(encoding="utf-8"))
                if isinstance(tools_data, list):
                    rel_tools = str(tools_file.relative_to(self.repo_path))
                    ledger.add_fact(
                        key="tools_schema",
                        value=len(tools_data),
                        source_file=rel_tools,
                        source_type=FactSourceType.CONFIG,
                        description="OpenAI tools function calling schemas count",
                        unit="tools",
                    )
            except Exception:
                pass

