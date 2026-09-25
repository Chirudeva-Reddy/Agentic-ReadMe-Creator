"""Tests for core data contracts and schemas."""

import json
from pathlib import Path
from agentic_readme.core.models import (
    ArchitectureNode,
    ClaimItem,
    FactsLedger,
    FactSourceType,
    FindingCategory,
    FindingSeverity,
    StorySpec,
    VerificationFinding,
    VerificationReport,
)


def test_facts_ledger_serialization(tmp_path: Path):
    ledger = FactsLedger(repo_name="demo-repo")
    ledger.add_fact(
        key="test_count",
        value=52,
        source_file="tests/",
        source_type=FactSourceType.TEST_RUN,
        description="Passing pytest test suite",
    )
    ledger.add_fact(
        key="python_version",
        value=">=3.11",
        source_file="pyproject.toml",
        source_type=FactSourceType.CONFIG,
    )

    save_file = tmp_path / "facts.json"
    ledger.save(save_file)
    assert save_file.exists()

    loaded = FactsLedger.load(save_file)
    assert loaded.repo_name == "demo-repo"
    assert loaded.get_fact("test_count").value == 52
    assert loaded.get_fact("python_version").value == ">=3.11"


def test_story_spec_yaml_roundtrip(tmp_path: Path):
    story = StorySpec(
        repo_name="duet-test",
        target_audience="Developers",
        hook="You pay for Claude and ChatGPT. On any given question you ask one of them.",
        problem="Models make confident errors that single sessions miss.",
        solution="duet runs both blind and surfaces only the disagreements.",
        key_claims=[
            ClaimItem(
                claim="Zero API keys required",
                evidence_file="duet",
                metrics={"keys_required": 0},
            )
        ],
        architecture_nodes=[
            ArchitectureNode(id="cli", label="duet CLI", role="entrypoint", source_file="duet")
        ],
        quickstart_commands=["duet 'my prompt'"],
        deliberate_omissions=["No consensus synthesis"],
    )

    yaml_file = tmp_path / "story.yaml"
    story.save_yaml(yaml_file)
    assert yaml_file.exists()

    loaded = StorySpec.load_yaml(yaml_file)
    assert loaded.repo_name == "duet-test"
    assert loaded.hook == story.hook
    assert len(loaded.key_claims) == 1
    assert loaded.key_claims[0].claim == "Zero API keys required"


def test_verification_report_counts():
    report = VerificationReport()
    assert report.passed is True
    assert report.fatal_count == 0

    report.add_finding(
        category=FindingCategory.VOICE_SLOP,
        severity=FindingSeverity.WARNING,
        message="Hype word detected",
    )
    assert report.passed is True  # Warning does not fail report
    assert report.warning_count == 1

    report.add_finding(
        category=FindingCategory.FACT_DRIFT,
        severity=FindingSeverity.FATAL,
        message="Badge says 52, text says 44",
    )
    assert report.passed is False
    assert report.fatal_count == 1
