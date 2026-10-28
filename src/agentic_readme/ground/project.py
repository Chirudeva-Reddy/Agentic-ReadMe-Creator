"""Work out what kind of project a repo is, by looking at its files.

detect_project(repo) answers four questions without running anything:
  - Which language is it?            (pyproject.toml -> Python, package.json -> Node, ...)
  - Which file starts it?            (main.py, cli.py, index.js, ...)
  - How do you test it and run it?   (pytest, npm test, cargo run, ...)
  - What are its main parts?         (top-level folders, used as boxes in the diagram)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_readme.models import ArchitectureNode


@dataclass
class Project:
    """What we learned about a repo from its file layout."""
    name: str
    path: Path
    language: str
    entrypoints: list[str]
    test_command: str | None
    run_command: str | None
    architecture_nodes: list[ArchitectureNode]


# Files that usually start a program, checked in this order.
PYTHON_ENTRYPOINTS = ["main.py", "app.py", "cli.py", "run.py"]  # then src/<package>/cli.py
NODE_ENTRYPOINTS = ["index.js", "src/index.ts", "main.js", "app.js"]
RUST_ENTRYPOINTS = ["src/main.rs", "src/lib.rs"]

# Folder names we can label with confidence. Labels stay neutral: a folder name is all we
# know, so we don't imply a domain.
KNOWN_FOLDERS = {
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

# Folders that are never a "main part" of the project.
SKIP_TOP_LEVEL = {"tests", "test", "venv", ".venv", "docs", "assets", "dist", "build", "__pycache__"}
SKIP_IN_SRC = {"tests", "test", "docs", "dist", "build", "__pycache__"}


def detect_project(repo: Path) -> Project:
    repo = Path(repo).resolve()
    language, entrypoints = _language_and_entrypoints(repo)
    test_command, run_command = _commands(repo, language, entrypoints)
    return Project(
        name=repo.name,
        path=repo,
        language=language,
        entrypoints=entrypoints,
        test_command=test_command,
        run_command=run_command,
        architecture_nodes=_architecture_nodes(repo, entrypoints),
    )


def _existing(repo: Path, candidates: list[str]) -> list[str]:
    """The candidate paths that exist in the repo, in order."""
    return [c for c in candidates if (repo / c).exists()]


def _language_and_entrypoints(repo: Path) -> tuple[str, list[str]]:
    py_files = list(repo.glob("*.py")) + list(repo.glob("src/**/*.py"))
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists() or py_files:
        entrypoints = _existing(repo, PYTHON_ENTRYPOINTS)
        entrypoints += sorted(str(p.relative_to(repo)) for p in repo.glob("src/*/cli.py"))
        if not entrypoints and py_files:
            entrypoints = [str(py_files[0].relative_to(repo))]
        return "Python", entrypoints

    if (repo / "package.json").exists():
        return "JavaScript/TypeScript", _existing(repo, NODE_ENTRYPOINTS)

    if (repo / "Cargo.toml").exists():
        return "Rust", _existing(repo, RUST_ENTRYPOINTS)

    sh_files = list(repo.glob("*.sh"))
    if sh_files:
        return "Bash", [str(f.relative_to(repo)) for f in sh_files]

    return "Unknown", []


def _commands(repo: Path, language: str, entrypoints: list[str]) -> tuple[str | None, str | None]:
    """The (test command, run command) a newcomer would type."""
    if language == "Python":
        has_tests = (repo / "tests").exists() or (repo / "test").exists()
        test_command = "pytest" if has_tests else None
        run_command = f"python3 {entrypoints[0]}" if entrypoints else None
        return test_command, run_command
    if language == "JavaScript/TypeScript":
        return "npm test", "npm start"
    if language == "Rust":
        return "cargo test", "cargo run"
    if language == "Bash" and entrypoints:
        return None, f"./{entrypoints[0]}"
    return None, None


def _folders(parent: Path, skip: set[str]) -> list[Path]:
    """Sub-folders of `parent` that could be a main part of the project."""
    return [
        p for p in sorted(parent.iterdir())  # sorted, so the diagram is the same on every machine
        if p.is_dir()
        and not p.name.startswith(".")
        and not p.name.endswith(".egg-info")
        and p.name not in skip
    ]


def _architecture_nodes(repo: Path, entrypoints: list[str]) -> list[ArchitectureNode]:
    """One diagram box for the entrypoint, then one per main folder (top level and src/)."""
    nodes: list[ArchitectureNode] = []

    if entrypoints:
        nodes.append(ArchitectureNode(
            id="entrypoint",
            label=f"CLI / Entrypoint ({Path(entrypoints[0]).name})",
            role="entrypoint",
            source_file=entrypoints[0],
        ))

    folders = _folders(repo, SKIP_TOP_LEVEL)
    if (repo / "src").is_dir():
        folders += _folders(repo / "src", SKIP_IN_SRC)

    seen_ids = set()
    for folder in folders:
        name = folder.name.lower()
        if name in KNOWN_FOLDERS:
            label, role = KNOWN_FOLDERS[name]
            node_id = name
        else:
            label = f"{folder.name.replace('_', ' ').title()} Module"
            role = "pipeline_stage"
            node_id = folder.name
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        nodes.append(ArchitectureNode(
            id=node_id,
            label=label,
            role=role,
            source_file=str(folder.relative_to(repo)),
        ))

    if not nodes:
        nodes = [
            ArchitectureNode(id="core", label="Core Processing Pipeline", role="pipeline_stage"),
            ArchitectureNode(id="output", label="Verified Output Artifacts", role="output"),
        ]
    return nodes
