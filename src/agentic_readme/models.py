"""The data shapes that every step passes around.

Two of them are saved in `.agentic-readme/` and act as contracts between the steps:

- FactsLedger -> facts.json : every number we know about the repo, with the file it came from
- StorySpec   -> story.yaml : the pitch, claims and quickstart (a human or the agent may edit it)

VerificationReport is what the checks return: a list of findings plus a pass/fail flag.

`BaseModel` comes from pydantic. It is a normal class whose fields have types; pydantic
checks the types and can turn the object into JSON and back.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _now() -> str:
    """The current UTC time as text, used to timestamp facts and reports."""
    return datetime.now(timezone.utc).isoformat()


# --- facts.json ------------------------------------------------------------------------

class FactSourceType(str, Enum):
    TEST_RUN = "test_run"
    CONFIG = "config"
    BENCHMARK = "benchmark"
    SOURCE_CODE = "source_code"
    GIT = "git"
    MANUAL = "manual"


class FactItem(BaseModel):
    """One fact read from the repo, e.g. test_count = 3 (from tests/)."""
    key: str
    value: str | int | float | bool | list[str]
    source_file: str
    source_type: FactSourceType = FactSourceType.SOURCE_CODE
    description: str = ""
    unit: str | None = None
    line_number: int | None = None
    verified_at: str = Field(default_factory=_now)


class FactsLedger(BaseModel):
    """All the facts for one repo. Nothing may claim a number that isn't in here."""
    repo_name: str
    generated_at: str = Field(default_factory=_now)
    facts: dict[str, FactItem] = Field(default_factory=dict)

    def add_fact(
        self,
        key: str,
        value: str | int | float | bool | list[str],
        source_file: str,
        source_type: FactSourceType = FactSourceType.SOURCE_CODE,
        description: str = "",
        unit: str | None = None,
        line_number: int | None = None,
    ) -> FactItem:
        item = FactItem(
            key=key,
            value=value,
            source_file=source_file,
            source_type=source_type,
            description=description,
            unit=unit,
            line_number=line_number,
        )
        self.facts[key] = item
        return item

    def get_fact(self, key: str) -> FactItem | None:
        return self.facts.get(key)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> FactsLedger:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


# --- story.yaml ------------------------------------------------------------------------

class ClaimItem(BaseModel):
    """One claim for the README, with the file that proves it and the numbers it uses."""
    claim: str
    evidence_file: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    verified: bool = True


class ArchitectureNode(BaseModel):
    """One box in the architecture diagram, taken from a real file or folder."""
    id: str
    label: str
    role: str = "pipeline_stage"  # entrypoint, pipeline_stage, guardrail, storage, output
    source_file: str | None = None
    technologies: list[str] = Field(default_factory=list)


class StorySpec(BaseModel):
    """The story the README tells. Producers read it; they never change it."""
    version: str = "1.0"
    repo_name: str
    target_audience: str
    hook: str  # one line naming the reader's problem
    problem: str
    solution: str
    key_claims: list[ClaimItem] = Field(default_factory=list)
    architecture_nodes: list[ArchitectureNode] = Field(default_factory=list)
    quickstart_commands: list[str] = Field(default_factory=list)
    deliberate_omissions: list[str] = Field(default_factory=list)  # honest trade-offs
    evidence_summary: str = ""
    created_at: str = Field(default_factory=_now)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(self.model_dump(), sort_keys=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> StorySpec:
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


# --- verification results --------------------------------------------------------------

class FindingSeverity(str, Enum):
    FATAL = "fatal"      # fails the run
    WARNING = "warning"  # reported, and verify tries to auto-fix it
    MINOR = "minor"      # reported only


class FindingCategory(str, Enum):
    FACT_DRIFT = "fact_drift"
    JARGON_LEAKAGE = "jargon_leakage"
    RENDER_ISSUE = "render_issue"
    VOICE_SLOP = "voice_slop"
    SIZE_LIMIT = "size_limit"
    BROKEN_LINK = "broken_link"


class VerificationFinding(BaseModel):
    """One problem found by a check, with what was expected and how to fix it."""
    category: FindingCategory
    severity: FindingSeverity
    message: str
    location: str | None = None
    expected: str | None = None
    actual: str | None = None
    suggested_fix: str | None = None


class VerificationReport(BaseModel):
    """Everything the checks found. `passed` turns False on the first fatal finding."""
    timestamp: str = Field(default_factory=_now)
    passed: bool = True
    facts_checked: int = 0
    findings: list[VerificationFinding] = Field(default_factory=list)

    @property
    def fatal_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.FATAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.WARNING)

    @property
    def minor_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.MINOR)

    def finding_lines(self) -> list[str]:
        """Each finding as text, followed by how to fix it (for an agent or a log)."""
        lines = []
        for f in self.findings:
            lines.append(f"- [{f.severity.value}] {f.category.value}: {f.message} (Location: {f.location or 'general'})")
            if f.suggested_fix:
                lines.append(f"  Fix: {f.suggested_fix}")
        return lines

    def add_finding(
        self,
        category: FindingCategory,
        severity: FindingSeverity,
        message: str,
        location: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
        suggested_fix: str | None = None,
    ) -> VerificationFinding:
        finding = VerificationFinding(
            category=category,
            severity=severity,
            message=message,
            location=location,
            expected=expected,
            actual=actual,
            suggested_fix=suggested_fix,
        )
        self.findings.append(finding)
        if severity == FindingSeverity.FATAL:
            self.passed = False
        return finding
