"""Tests for Phase 1 Producers (Diagram, Demo, Video, Writer)."""

import json
from pathlib import Path
from agentic_readme.core.models import (
    ArchitectureNode,
    ClaimItem,
    FactsLedger,
    FactSourceType,
    StorySpec,
)
from agentic_readme.produce.demo_agent import DemoAgent
from agentic_readme.produce.diagram_agent import DiagramAgent
from agentic_readme.produce.video_agent import VideoAgent
from agentic_readme.produce.writer_agent import WriterAgent


def _create_mock_contracts() -> tuple[StorySpec, FactsLedger]:
    ledger = FactsLedger(repo_name="verified-tool")
    ledger.add_fact("license", "MIT", "LICENSE", FactSourceType.SOURCE_CODE)
    ledger.add_fact("python_version", "3.11+", "pyproject.toml", FactSourceType.CONFIG)
    ledger.add_fact("test_count", 52, "tests/", FactSourceType.TEST_RUN)

    story = StorySpec(
        repo_name="verified-tool",
        target_audience="Engineers",
        hook="Tired of broken documentation and drifted metrics.",
        problem="Documentation drifts from actual code execution.",
        solution="Verified pipeline generating code-grounded README assets.",
        key_claims=[
            ClaimItem(
                claim="52 passing tests verified",
                evidence_file="tests/",
                metrics={"tests": 52},
            )
        ],
        architecture_nodes=[
            ArchitectureNode(id="cli", label="CLI Entrypoint", role="entrypoint"),
            ArchitectureNode(id="core", label="Grounding Engine", role="pipeline_stage"),
            ArchitectureNode(id="guard", label="Claim Auditor", role="guardrail"),
        ],
        quickstart_commands=["pip install -e .", "pytest"],
        deliberate_omissions=["No unverified text generation"],
    )
    return story, ledger


def test_diagram_agent(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = DiagramAgent(tmp_path)
    assets = agent.produce(story, ledger)

    assert assets["excalidraw"].exists()
    assert assets["light_svg"].exists()
    assert assets["dark_svg"].exists()

    # Validate excalidraw JSON structure
    excal_content = json.loads(assets["excalidraw"].read_text(encoding="utf-8"))
    assert excal_content["type"] == "excalidraw"
    assert len(excal_content["elements"]) > 0

    # Validate SVGs
    light_content = assets["light_svg"].read_text(encoding="utf-8")
    dark_content = assets["dark_svg"].read_text(encoding="utf-8")
    assert "<svg" in light_content and "CLI Entrypoint" in light_content
    assert "<svg" in dark_content and "#0d1117" in dark_content


def test_demo_agent(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = DemoAgent(tmp_path)
    res = agent.produce(story, ledger)

    assert res["tape_file"].exists()
    assert res["hero_asset"].exists()
    tape_text = res["tape_file"].read_text(encoding="utf-8")
    assert 'Type "pytest"' in tape_text
    assert res["max_size_bytes"] == 5 * 1024 * 1024


def test_video_agent(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = VideoAgent(tmp_path)
    res = agent.produce(story, ledger)

    assert res["spec_file"].exists()
    assert res["scene_table"].exists()
    spec = json.loads(res["spec_file"].read_text(encoding="utf-8"))
    assert spec["duration_seconds"] == 20
    assert len(spec["scenes"]) == 4


def test_writer_agent_house_style(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = WriterAgent(tmp_path)
    readme_path = agent.produce(story, ledger)

    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")

    # Check centered title and italic hook
    assert '<h1 align="center">verified-tool</h1>' in content
    assert "<em>Tired of broken documentation and drifted metrics.</em>" in content

    # Check flat-square badges linking to evidence
    assert "style=flat-square" in content
    assert 'href="tests/"' in content
    assert "tests-52%20passed" in content

    # Check architecture <picture> with dark mode
    assert "<picture>" in content
    assert "(prefers-color-scheme: dark)" in content
    assert "architecture.excalidraw" in content

    # Check evidence table and deliberate omissions
    assert "## Evidence & Ground Truth" in content
    assert "## Deliberately not included" in content
