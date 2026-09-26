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


def test_facts_extractor_nested_tests_and_evidence(tmp_path: Path):
    """Verifies that nested test subdirectories and evidence files are discovered."""
    # Nested test file
    nested_dir = tmp_path / "tests" / "submodule" / "unit"
    nested_dir.mkdir(parents=True)
    (nested_dir / "test_nested.py").write_text("def test_nested_one(): pass\ndef test_nested_two(): pass\n", encoding="utf-8")

    # Body2health reference evidence file
    (tmp_path / "deva_gate_accepted.json").write_text("""{
        "accuracy": 0.985,
        "f1_score": 0.972,
        "latency_ms": 14.2
    }""", encoding="utf-8")

    # Description in pyproject.toml
    (tmp_path / "pyproject.toml").write_text("""[project]
name = "deva-health"
description = "Arrhythmia detection from wearable ECG signals"
version = "2.1.0"
""", encoding="utf-8")

    extractor = FactsExtractor(tmp_path)
    ledger = extractor.extract_all("deva-health")

    # Tests from nested dir
    assert ledger.get_fact("test_count").value == 2
    # Description
    assert ledger.get_fact("project_description").value == "Arrhythmia detection from wearable ECG signals"
    # Evidence metrics
    assert ledger.get_fact("metric_accuracy").value == 0.985
    assert ledger.get_fact("metric_latency_ms").value == 14.2


def test_story_builder_grounded_in_project_description(tmp_path: Path):
    """Verifies that StoryBuilder dynamically adapts to the domain instead of hardcoding self-referential text."""
    (tmp_path / "pyproject.toml").write_text("""[project]
name = "car-triage"
description = "Explainable collision damage triage"
version = "1.0.0"
""", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ready')", encoding="utf-8")

    analyst = RepoAnalyst(tmp_path)
    analysis = analyst.analyze()
    builder = StoryBuilder(analysis)
    story = builder.build_story()

    # Story problem and solution must mention the actual domain, NOT documentation drift!
    assert "explainable collision damage triage" in story.solution.lower()
    assert "documentation pipelines" not in story.problem.lower()
    assert "opaque estimates" in story.problem.lower()


def test_facts_extractor_counts_code_under_dotted_parent_dir(tmp_path: Path):
    """A repo living under a dot-directory (e.g. ~/.projects) must still be counted."""
    repo = tmp_path / ".projects" / "tip-splitter"
    repo.mkdir(parents=True)
    (repo / "cli.py").write_text("print('hi')\nprint('bye')\n", encoding="utf-8")

    ledger = FactsExtractor(repo).extract_all()

    assert ledger.get_fact("python_loc").value == 2
    assert ledger.get_fact("python_loc").source_file == "."


def test_facts_extractor_counts_node_test_cases_not_files(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "habit-streak", "version": "1.0.0"}', encoding="utf-8")
    (tmp_path / "streak.test.js").write_text('test("a", () => {});\ntest("b", () => {});\n', encoding="utf-8")

    ledger = FactsExtractor(tmp_path).extract_all()

    assert ledger.get_fact("test_count").value == 2
