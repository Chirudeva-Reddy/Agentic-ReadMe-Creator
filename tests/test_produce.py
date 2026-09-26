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
    assert assets["static_svg"].exists()

    # Validate excalidraw JSON structure
    excal_content = json.loads(assets["excalidraw"].read_text(encoding="utf-8"))
    assert excal_content["type"] == "excalidraw"
    assert len(excal_content["elements"]) > 0

    # Validate SVGs
    light_content = assets["light_svg"].read_text(encoding="utf-8")
    dark_content = assets["dark_svg"].read_text(encoding="utf-8")
    static_content = assets["static_svg"].read_text(encoding="utf-8")
    assert "<svg" in light_content and "CLI Entrypoint" in light_content
    assert "<svg" in dark_content and "#0d1117" in dark_content
    assert "<svg" in static_content and "#24292f" in static_content



def test_demo_agent(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = DemoAgent(tmp_path)
    res = agent.produce(story, ledger)

    assert res["tape_file"].exists()
    assert res["hero_asset"].exists()
    assert res["static_asset"].exists()
    tape_text = res["tape_file"].read_text(encoding="utf-8")
    assert 'Type "pytest"' in tape_text
    assert res["max_size_bytes"] == 5 * 1024 * 1024


def test_demo_agent_xml_escaping(tmp_path: Path):
    """Ensure DemoAgent properly escapes special characters in XML/SVG."""
    import xml.etree.ElementTree as ET

    story, ledger = _create_mock_contracts()
    story.repo_name = "Agent & Tool <v1.0>"
    story.quickstart_commands = ['git clone <repo-url> && cd "my tool"']
    story.key_claims = [
        ClaimItem(claim='100% verified & tested <invariants>', evidence_file="tests/")
    ]

    agent = DemoAgent(tmp_path)
    res = agent.produce(story, ledger)

    svg_path = res["hero_asset"]
    static_svg_path = res["static_asset"]
    assert svg_path.exists()
    assert static_svg_path.exists()

    # Must parse without XML syntax errors
    tree = ET.parse(svg_path)
    root = tree.getroot()
    assert root.attrib["width"] == "800"
    assert root.attrib["height"] == "380"
    assert root.attrib["viewBox"] == "0 0 800 380"
    assert root.attrib["version"] == "1.1"

    content = svg_path.read_text(encoding="utf-8")
    assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "@keyframes blink" in content
    assert "&amp;&amp;" in content or "&amp;" in content

    # Static fallback should also be valid XML
    static_tree = ET.parse(static_svg_path)
    assert static_tree.getroot().attrib["viewBox"] == "0 0 800 380"


def test_video_agent(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    agent = VideoAgent(tmp_path)
    res = agent.produce(story, ledger)

    assert res["spec_file"].exists()
    assert res["scene_table"].exists()
    spec = json.loads(res["spec_file"].read_text(encoding="utf-8"))
    assert spec["duration_seconds"] == 20
    assert spec["status"] == "storyboard_only"
    assert sum(s["duration_seconds"] for s in spec["scenes"]) == 20

    # Problem-first: opens on the hook, names the project only in the reveal
    hook, reveal = spec["scenes"][0], spec["scenes"][1]
    assert hook["narration"] == story.hook
    assert "verified-tool" not in hook["narration"]
    assert reveal["narration"].startswith("verified-tool")

    # Grounded: proof scene reuses real claims; no tool boilerplate leaks into the user's video
    assert "52 passing tests verified" in spec["scenes"][3]["narration"]
    assert "zero-drift" not in res["scene_table"].read_text(encoding="utf-8")
    assert spec["deliverables"]["gif"] == spec["github_safe_embed"]["preview_gif"] == "assets/video/launch-video.gif"


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

    # Check hero demo <picture> with static fallback and architecture <picture> with dark mode
    assert "<picture>" in content
    assert "(prefers-reduced-motion: reduce)" in content
    assert "assets/demo/hero-demo-static.svg" in content
    assert "(prefers-color-scheme: dark)" in content
    assert "architecture.excalidraw" in content

    # Check evidence table and deliberate omissions
    assert "## Evidence & Ground Truth" in content
    assert "## Deliberately not included" in content


def test_writer_without_launch_video_labels_svg_as_illustration(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    content = WriterAgent(tmp_path).produce(story, ledger).read_text(encoding="utf-8")

    assert 'src="assets/demo/hero-demo.svg"' in content
    assert "not a screen recording" in content
    assert "launch-video" not in content
    assert "That run is real" not in content


def test_writer_embeds_launch_video_when_rendered(tmp_path: Path):
    video_dir = tmp_path / "assets" / "video"
    video_dir.mkdir(parents=True)
    for name in ("launch-video.gif", "launch-video.mp4", "launch-poster.jpg"):
        (video_dir / name).write_bytes(b"x")

    story, ledger = _create_mock_contracts()
    content = WriterAgent(tmp_path).produce(story, ledger).read_text(encoding="utf-8")

    # GIF preview wrapped in a link to the MP4, poster for reduced motion, no <video> tag
    assert '<a href="assets/video/launch-video.mp4">' in content
    assert 'src="assets/video/launch-video.gif"' in content
    assert 'srcset="assets/video/launch-poster.jpg"' in content
    assert "<video" not in content
    assert "hero-demo.svg" not in content


def test_video_outro_without_git_remote_names_install_once(tmp_path: Path):
    story, ledger = _create_mock_contracts()
    story.quickstart_commands = ["pip install -e .", "python3 cli.py"]
    outro = VideoAgent(tmp_path).produce(story, ledger)["scenes"][-1]

    assert outro["narration"] == "pip install -e ."
    assert outro["visual"] == "Install command `pip install -e .`."
    assert "One command: python3 cli.py." == VideoAgent(tmp_path).produce(story, ledger)["scenes"][2]["narration"]
