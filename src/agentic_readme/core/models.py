"""Core data contracts and schemas for Agentic ReadMe Creator.

Ensures that the pipeline is strictly grounded in immutable StorySpec
and FactsLedger artifacts before any generative fan-out occurs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class FactSourceType(str, Enum):
    TEST_RUN = "test_run"
    CONFIG = "config"
    BENCHMARK = "benchmark"
    SOURCE_CODE = "source_code"
    GIT = "git"
    MANUAL = "manual"


class FactItem(BaseModel):
    """A single deterministic fact extracted from code or execution."""
    key: str
    value: Union[str, int, float, bool, List[str]]
    source_file: str
    source_type: FactSourceType = FactSourceType.SOURCE_CODE
    description: str = ""
    unit: Optional[str] = None
    line_number: Optional[int] = None
    verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FactsLedger(BaseModel):
    """Immutable ledger of all verified numbers, names, and parameters.

    Every generator agent reads from this; no agent may introduce
    facts not registered in or verifiable against this ledger.
    """
    repo_name: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    facts: Dict[str, FactItem] = Field(default_factory=dict)

    def add_fact(
        self,
        key: str,
        value: Union[str, int, float, bool, List[str]],
        source_file: str,
        source_type: FactSourceType = FactSourceType.SOURCE_CODE,
        description: str = "",
        unit: Optional[str] = None,
        line_number: Optional[int] = None,
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

    def get_fact(self, key: str) -> Optional[FactItem]:
        return self.facts.get(key)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def save(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path]) -> FactsLedger:
        content = Path(path).read_text(encoding="utf-8")
        return cls.model_validate_json(content)


class ClaimItem(BaseModel):
    """A core claim about the project grounded in verifiable evidence."""
    claim: str
    evidence_file: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    verified: bool = True


class ArchitectureNode(BaseModel):
    """Component or stage derived from real code, not vague abstractions."""
    id: str
    label: str
    role: str = "pipeline_stage"  # entrypoint, pipeline_stage, guardrail, storage, output
    source_file: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class StorySpec(BaseModel):
    """Immutable narrative contract agreed upon after Phase 0 Grounding.

    Phase 1 producers (Diagram, Demo, Video, Writer) MUST strictly adhere to
    this story without deviating on numbers, pitch, or structure.
    """
    version: str = "1.0"
    repo_name: str
    target_audience: str
    hook: str  # Pain-first 1-line hook (e.g. duet's "You pay for Claude and ChatGPT...")
    problem: str
    solution: str
    key_claims: List[ClaimItem] = Field(default_factory=list)
    architecture_nodes: List[ArchitectureNode] = Field(default_factory=list)
    quickstart_commands: List[str] = Field(default_factory=list)
    deliberate_omissions: List[str] = Field(default_factory=list)  # Honest engineering tradeoffs
    evidence_summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def save_yaml(self, path: Union[str, Path]) -> None:
        import yaml
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump()
        p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @classmethod
    def load_yaml(cls, path: Union[str, Path]) -> StorySpec:
        import yaml
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls.model_validate(data)


class FindingSeverity(str, Enum):
    FATAL = "Fatal Functional Bug"
    WARNING = "Shallow Verification"
    MINOR = "Minor Robustness Risk"


class FindingCategory(str, Enum):
    FACT_DRIFT = "fact_drift"
    JARGON_LEAKAGE = "jargon_leakage"
    RENDER_ISSUE = "render_issue"
    VOICE_SLOP = "voice_slop"
    SIZE_LIMIT = "size_limit"
    BROKEN_LINK = "broken_link"


class VerificationFinding(BaseModel):
    """An issue detected during Phase 2 cross-asset verification."""
    category: FindingCategory
    severity: FindingSeverity
    message: str
    location: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    suggested_fix: Optional[str] = None


class VerificationReport(BaseModel):
    """Consolidated audit report from Phase 2 verifiers."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    passed: bool = True
    facts_checked: int = 0
    findings: List[VerificationFinding] = Field(default_factory=list)

    @property
    def fatal_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.FATAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.WARNING)

    @property
    def minor_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.MINOR)

    def add_finding(
        self,
        category: FindingCategory,
        severity: FindingSeverity,
        message: str,
        location: Optional[str] = None,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        suggested_fix: Optional[str] = None,
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
