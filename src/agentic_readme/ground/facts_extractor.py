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

        # Count python source files and loc
        py_files = list(self.repo_path.glob("**/*.py"))
        py_files = [f for f in py_files if not any(part.startswith(".") or part in ("venv", ".venv", "build", "dist") for part in f.parts)]
        if py_files:
            total_loc = sum(len(f.read_text(encoding="utf-8", errors="ignore").splitlines()) for f in py_files)
            ledger.add_fact(
                key="python_file_count",
                value=len(py_files),
                source_file="src/",
                source_type=FactSourceType.SOURCE_CODE,
                description="Number of Python source files",
                unit="files",
            )
            ledger.add_fact(
                key="python_loc",
                value=total_loc,
                source_file="src/",
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
        """Scan test directories and count test definitions deterministically using AST."""
        test_dir = self.repo_path / "tests"
        if not test_dir.exists():
            test_dir = self.repo_path / "test"

        if test_dir.exists():
            test_files = list(test_dir.glob("test_*.py")) + list(test_dir.glob("*_test.py"))
            count = 0
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

            if count > 0:
                ledger.add_fact(
                    key="test_count",
                    value=count,
                    source_file=str(test_dir.relative_to(self.repo_path)),
                    source_type=FactSourceType.TEST_RUN,
                    description="Total verified test case count",
                    unit="tests",
                )

    def _extract_data_and_evidence(self, ledger: FactsLedger) -> None:
        """Look for benchmark files or metrics files (e.g. data/*.json, results/*.json)."""
        evidence_candidates = [
            "data/benchmark_results.json",
            "data/eval_results.json",
            "results.json",
            "metrics.json",
            "benchmark.json",
        ]
        for ec in evidence_candidates:
            target = self.repo_path / ec
            if target.exists():
                try:
                    data = json.loads(target.read_text(encoding="utf-8", errors="ignore"))
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, (int, float, str)):
                                ledger.add_fact(
                                    key=f"metric_{k}",
                                    value=v,
                                    source_file=ec,
                                    source_type=FactSourceType.BENCHMARK,
                                    description=f"Benchmark metric: {k}",
                                )
                except Exception:
                    pass
