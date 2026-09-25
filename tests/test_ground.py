"""Tests for Phase 0 Grounding components."""

from pathlib import Path
from agentic_readme.ground.facts_extractor import FactsExtractor
from agentic_readme.ground.repo_analyst import RepoAnalyst
from agentic_readme.ground.story_builder import StoryBuilder


def test_facts_extractor_python_repo(tmp_path: Path):
    # Setup mock python project
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""[project]
name = "mock-pipeline"
version = "0.2.1"
requires-python = ">=3.11"
""", encoding="utf-8")

    license_file = tmp_path / "LICENSE"
    license_file.write_text("MIT License\nPermission is hereby granted...", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello world')\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_suite.py").write_text("""
def test_one():
    assert True

def test_two():
    assert 1 == 1

def test_three():
    pass
""", encoding="utf-8")

    extractor = FactsExtractor(tmp_path)
    ledger = extractor.extract_all(repo_name="mock-pipeline")

    assert ledger.repo_name == "mock-pipeline"
    assert ledger.get_fact("python_version").value == ">=3.11"
    assert ledger.get_fact("project_version").value == "0.2.1"
    assert ledger.get_fact("license").value == "MIT"
    assert ledger.get_fact("test_count").value == 3


def test_repo_analyst_and_story_builder(tmp_path: Path):
    # Setup mock project
    (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.12"\n', encoding="utf-8")
    (tmp_path / "app.py").write_text("import sys\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    analyst = RepoAnalyst(tmp_path)
    analysis = analyst.analyze()

    assert analysis.primary_language == "Python"
    assert "app.py" in analysis.entrypoints
    assert analysis.test_command == "pytest"

    builder = StoryBuilder(analysis)
    story = builder.build_story(custom_hook="Eliminating documentation drift.")

    assert story.hook == "Eliminating documentation drift."
    assert len(story.key_claims) >= 1
    assert any("test" in c.claim.lower() for c in story.key_claims)
