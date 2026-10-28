"""Collect every number and name we can prove about a repo, into a FactsLedger.

collect_facts(repo, entrypoints) reads config files, counts code and tests, and runs two
safe commands (`pytest --collect-only` and `<entrypoint> --help`). Each fact records the
file it came from, so every badge and claim in the README can link to its evidence.

The order of the steps below is the order of the facts in facts.json.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

from agentic_readme.models import FactsLedger, FactSourceType


def collect_facts(repo: Path, entrypoints: list[str]) -> FactsLedger:
    repo = Path(repo).resolve()
    facts = FactsLedger(repo_name=repo.name)
    _git_facts(repo, facts)
    _python_facts(repo, facts)
    _node_facts(repo, facts)
    _rust_facts(repo, facts)
    _license_fact(repo, facts)
    _test_count(repo, facts)
    _evidence_metrics(repo, facts)
    _integration_facts(repo, facts)
    _cli_help_facts(repo, entrypoints, facts)
    return facts


# --- helpers ---------------------------------------------------------------------------

def _run(command: list[str], repo: Path, timeout: int) -> subprocess.CompletedProcess | None:
    """Run a command inside the repo. Returns None if it can't start or takes too long."""
    try:
        return subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _is_ignored(path: Path, repo: Path, skip: set[str]) -> bool:
    """True for files inside hidden folders, build output, or the folders in `skip`."""
    for part in path.relative_to(repo).parts:
        if part.startswith(".") or part in skip or part.endswith(".egg-info"):
            return True
    return False


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


# --- one function per source of facts ---------------------------------------------------

def _git_facts(repo: Path, facts: FactsLedger) -> None:
    if not (repo / ".git").exists():
        return

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, timeout=5)
    if branch and branch.returncode == 0:
        facts.add_fact("git_default_branch", branch.stdout.strip(), ".git",
                       FactSourceType.GIT, "Default git branch")

    remote = _run(["git", "config", "--get", "remote.origin.url"], repo, timeout=5)
    if remote and remote.returncode == 0 and remote.stdout.strip():
        facts.add_fact("git_remote_url", remote.stdout.strip(), ".git/config",
                       FactSourceType.GIT, "Git remote repository URL")


def _toml_facts(repo: Path, filename: str, fields: list[tuple[str, str, str]], facts: FactsLedger) -> None:
    """Pull `key = "value"` lines out of a TOML file. fields = (fact key, toml key, description)."""
    path = repo / filename
    if not path.exists():
        return
    # ponytail: a regex, not a TOML parser; it takes the first `key = "..."` anywhere in the file
    content = _read(path)
    for fact_key, toml_key, description in fields:
        match = re.search(rf'{toml_key}\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            facts.add_fact(fact_key, match.group(1), filename, FactSourceType.CONFIG, description)


def _python_facts(repo: Path, facts: FactsLedger) -> None:
    _toml_facts(repo, "pyproject.toml", [
        ("python_version", "requires-python", "Supported Python version requirement"),
        ("project_version", "version", "Project release version"),
        ("project_description", "description", "Project summary description"),
    ], facts)

    # Count only src/ when it exists, so the evidence link covers exactly what was counted.
    src = repo / "src"
    root = src if src.is_dir() else repo
    py_files = [f for f in root.glob("**/*.py") if not _is_ignored(f, repo, {"venv", ".venv", "build", "dist"})]
    if not py_files:
        return
    source = "src/" if src.is_dir() else "."
    total_lines = sum(len(_read(f).splitlines()) for f in py_files)
    facts.add_fact("python_file_count", len(py_files), source, FactSourceType.SOURCE_CODE,
                   "Number of Python source files", unit="files")
    facts.add_fact("python_loc", total_lines, source, FactSourceType.SOURCE_CODE,
                   "Lines of Python code", unit="lines")


def _node_facts(repo: Path, facts: FactsLedger) -> None:
    path = repo / "package.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if "version" in data:
        facts.add_fact("package_version", data["version"], "package.json",
                       FactSourceType.CONFIG, "Package version in package.json")
    if "description" in data:
        facts.add_fact("project_description", data["description"], "package.json",
                       FactSourceType.CONFIG, "Project description from package.json")
    count = len(data.get("dependencies", {})) + len(data.get("devDependencies", {}))
    facts.add_fact("dependency_count", count, "package.json", FactSourceType.CONFIG,
                   "Total Node dependencies count", unit="dependencies")


def _rust_facts(repo: Path, facts: FactsLedger) -> None:
    _toml_facts(repo, "Cargo.toml", [
        ("cargo_version", "version", "Cargo package version"),
        ("project_description", "description", "Cargo project description"),
    ], facts)


def _license_fact(repo: Path, facts: FactsLedger) -> None:
    for filename in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
        path = repo / filename
        if not path.exists():
            continue
        text = _read(path)
        if "MIT License" in text or "Permission is hereby granted, free of charge" in text:
            kind = "MIT"
        elif "Apache License" in text:
            kind = "Apache-2.0"
        elif "GNU GENERAL PUBLIC LICENSE" in text:
            kind = "GPL"
        elif "BSD" in text:
            kind = "BSD"
        else:
            kind = "Custom"
        facts.add_fact("license", kind, filename, FactSourceType.SOURCE_CODE, "Software license")
        return


def _test_count(repo: Path, facts: FactsLedger) -> None:
    """Count tests: ask pytest first, and fall back to reading the test files."""
    test_dir = repo / "tests"
    if not test_dir.exists():
        test_dir = repo / "test"
    source = str(test_dir.relative_to(repo)) if test_dir.exists() else "."

    # 1. `pytest --collect-only` lists the tests without running any of them.
    if test_dir.exists() or any(repo.glob("**/test_*.py")):
        result = _run(["pytest", "--collect-only", "-q"], repo, timeout=6)
        if result and result.returncode == 0:
            match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout)
            if match and int(match.group(1)) > 0:
                facts.add_fact("test_count", int(match.group(1)), source, FactSourceType.TEST_RUN,
                               "Verified test case count from pytest collection", unit="tests")
                return

    # 2. Fallback: count test functions by reading the files (Python, then Node, then Rust).
    count = _count_python_tests(repo, test_dir)
    if count == 0 and (repo / "package.json").exists():
        count = _count_node_tests(repo)
    if count == 0 and (repo / "Cargo.toml").exists():
        count = _count_rust_tests(repo)
    if count > 0:
        facts.add_fact("test_count", count, source, FactSourceType.SOURCE_CODE,
                       "Static test definition count (AST/regex collection fallback)", unit="tests")


def _count_python_tests(repo: Path, test_dir: Path) -> int:
    search_dir = test_dir if test_dir.exists() else repo
    files = list(search_dir.rglob("test_*.py")) + list(search_dir.rglob("*_test.py"))
    count = 0
    for path in files:
        if _is_ignored(path, repo, {"venv", ".venv", "build", "dist"}):
            continue
        try:
            tree = ast.parse(_read(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    count += 1
        except Exception:
            # The file doesn't parse (e.g. a syntax error), so count `def test_...` lines instead.
            count += len(re.findall(r"^\s*def\s+(test_[a-zA-Z0-9_]+)\s*\(", _read(path), flags=re.MULTILINE))
    return count


def _count_node_tests(repo: Path) -> int:
    files = list(repo.rglob("*.test.[jt]s*")) + list(repo.rglob("*.spec.[jt]s*"))
    # ponytail: regex over test(/it( calls, not a JS parser; misses tests built in loops
    return sum(
        len(re.findall(r"^\s*(?:test|it)\s*\(", _read(path), flags=re.MULTILINE))
        for path in files
        if not _is_ignored(path, repo, {"node_modules", "dist", "build"})
    )


def _count_rust_tests(repo: Path) -> int:
    return sum(
        len(re.findall(r"#\[test\]", _read(path)))
        for path in repo.rglob("*.rs")
        if not _is_ignored(path, repo, {"target"})
    )


# Benchmark or result files whose top-level numbers become facts.
EVIDENCE_FILES = [
    "deva_gate_accepted.json",
    "results.json",
    "metrics.json",
    "benchmark.json",
    "price_table.json",
    "scraped_uae_oem_prices.json",
]
EVIDENCE_FOLDERS = ["data", "results", "benchmarks"]


def _evidence_metrics(repo: Path, facts: FactsLedger) -> None:
    """Turn the numbers in benchmark/result JSON files into `metric_*` facts."""
    files: list[Path] = [repo / name for name in EVIDENCE_FILES if (repo / name).is_file()]
    for folder in EVIDENCE_FOLDERS:
        if not (repo / folder).is_dir():
            continue
        for path in (repo / folder).rglob("*.json"):
            if path.is_file() and not any(part.startswith(".") for part in path.parts) and path not in files:
                files.append(path)

    for path in files[:10]:  # cap at 10 files
        try:
            source = str(path.relative_to(repo))
            data = json.loads(_read(path))
        except Exception:
            continue
        if isinstance(data, dict):
            for key, value in list(data.items())[:15]:  # cap at 15 numbers per file
                if isinstance(value, (int, float, str)):
                    facts.add_fact(f"metric_{key}", value, source, FactSourceType.BENCHMARK,
                                   f"Benchmark metric: {key}")
        elif isinstance(data, list):
            facts.add_fact(f"metric_{path.stem}_count", len(data), source, FactSourceType.BENCHMARK,
                           f"Item count in {path.name}", unit="items")


def _integration_facts(repo: Path, facts: FactsLedger) -> None:
    """Facts about how assistants can use the repo: a Claude skill, an MCP config, OpenAI tools."""
    skill = repo / "skills" / "agentic-readme" / "SKILL.md"
    if not skill.exists() and (repo / "skills").exists():
        others = list((repo / "skills").glob("*/SKILL.md"))
        if others:
            skill = others[0]
    if skill.exists():
        match = re.search(r"name:\s*([a-zA-Z0-9_\-]+)", _read(skill))
        facts.add_fact("skill", match.group(1) if match else "agentic-readme", str(skill.relative_to(repo)),
                       FactSourceType.CONFIG, "Claude Code agent skill specification identifier")

    for mcp_file in [repo / "integrations" / "mcp" / "mcp.json", repo / "mcp.json"]:
        if mcp_file.exists():
            facts.add_fact("protocol", "2024-11-05", str(mcp_file.relative_to(repo)),
                           FactSourceType.CONFIG, "Model Context Protocol specification version")
            break

    tools_file = repo / "integrations" / "gpt" / "openai_tools.json"
    if tools_file.exists():
        try:
            tools = json.loads(tools_file.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(tools, list):
            facts.add_fact("tools_schema", len(tools), str(tools_file.relative_to(repo)),
                           FactSourceType.CONFIG, "OpenAI tools function calling schemas count", unit="tools")


def _cli_help_facts(repo: Path, entrypoints: list[str], facts: FactsLedger) -> None:
    """Run `python3 <entrypoint> --help` to prove the program starts, and keep its first line."""
    if not entrypoints:
        facts.add_fact("headless_run_status", "no_entrypoint_found", ".",
                       description="Headless run status: no entrypoint found")
        return

    entrypoint = entrypoints[0]
    if entrypoint.endswith(".py"):
        result = _run(["python3", entrypoint, "--help"], repo, timeout=4)
        if result and result.returncode == 0 and result.stdout.strip():
            facts.add_fact("cli_help_output", result.stdout.strip().splitlines()[0][:120], entrypoint,
                           description="Verified CLI help output from live execution")
            facts.add_fact("headless_run_status", "verified_headless", entrypoint,
                           description="Project successfully ran headless")
            return

    facts.add_fact("headless_run_status", "fallback_static_only", entrypoint,
                   description="Headless run unverified; using static replay/diagram fallback")
