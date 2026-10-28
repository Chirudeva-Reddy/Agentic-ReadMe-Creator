"""Where the locked contracts (story.yaml, facts.json) live in a project."""

from __future__ import annotations

from pathlib import Path

CONTRACTS_DIR = ".agentic-readme"


def contract_path(root: Path, name: str) -> Path:
    """Locate story.yaml / facts.json under root/.agentic-readme/.

    Repos grounded before the folder existed keep theirs at the root; that copy is used
    until a new one is written.
    """
    new = Path(root) / CONTRACTS_DIR / name
    legacy = Path(root) / name
    return legacy if legacy.exists() and not new.exists() else new
