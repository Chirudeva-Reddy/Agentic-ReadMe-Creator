"""End-to-end pipeline integration tests for Agentic ReadMe Creator."""

from pathlib import Path
from agentic_readme.core.runner import PipelineRunner


def test_full_pipeline_run_on_sample_repo(tmp_path: Path):
    """Run full 3-phase pipeline on a mock repository."""
    # 1. Prepare sample repository
    repo_dir = tmp_path / "sample_service"
    repo_dir.mkdir()

    (repo_dir / "pyproject.toml").write_text("""[project]
name = "sample_service"
version = "1.0.0"
requires-python = ">=3.11"
""", encoding="utf-8")

    (repo_dir / "LICENSE").write_text("MIT License\nPermission is hereby granted...", encoding="utf-8")

    src_dir = repo_dir / "src" / "sample_service"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text("def run(): return 42\n", encoding="utf-8")

    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("""
def test_one():
    assert True

def test_two():
    assert 2 == 2
""", encoding="utf-8")

    # 2. Run pipeline
    runner = PipelineRunner(repo_dir, output_dir=repo_dir)
    res = runner.run_all(auto_approve_gate=True)

    # 3. Assert Phase 0 contracts
    assert (repo_dir / "story.yaml").exists()
    assert (repo_dir / "facts.json").exists()
    assert res["facts"].get_fact("test_count").value == 2
    assert res["facts"].get_fact("license").value == "MIT"

    # 4. Assert Phase 1 assets
    assert (repo_dir / "assets" / "diagrams" / "architecture.excalidraw").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture.svg").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture-dark.svg").exists()
    assert (repo_dir / "assets" / "diagrams" / "architecture-static.svg").exists()
    assert (repo_dir / "assets" / "demo" / "demo.tape").exists()

    assert (repo_dir / "assets" / "demo" / "hero-demo.svg").exists()
    assert (repo_dir / "assets" / "video" / "brag_spec.json").exists()
    assert (repo_dir / "README.md").exists()

    # 5. Assert Phase 2 verification
    assert res["passed"] is True
    report = res["verification_report"]
    assert report.fatal_count == 0

    # 6. Check content of generated README
    readme_text = (repo_dir / "README.md").read_text(encoding="utf-8")
    assert '<h1 align="center">sample_service</h1>' in readme_text
    assert "tests-2%20passed" in readme_text
    assert "architecture.excalidraw" in readme_text
    assert "## Evidence & Ground Truth" in readme_text
