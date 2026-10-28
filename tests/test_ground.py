"""Tests for ground/: project detection, fact collection, and the story draft."""

from pathlib import Path
from agentic_readme.ground.facts import collect_facts
from agentic_readme.ground.project import detect_project
from agentic_readme.ground.story import build_story


def test_collect_facts_python_repo(tmp_path: Path):
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

    ledger = collect_facts(tmp_path, entrypoints=[])

    assert ledger.repo_name == tmp_path.name
    assert ledger.get_fact("python_version").value == ">=3.11"
    assert ledger.get_fact("project_version").value == "0.2.1"
    assert ledger.get_fact("license").value == "MIT"
    assert ledger.get_fact("test_count").value == 3


def test_detect_project_and_build_story(tmp_path: Path):
    # Setup mock project
    (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.12"\n', encoding="utf-8")
    (tmp_path / "app.py").write_text("import sys\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    project = detect_project(tmp_path)
    facts = collect_facts(tmp_path, project.entrypoints)

    assert project.language == "Python"
    assert "app.py" in project.entrypoints
    assert project.test_command == "pytest"

    story = build_story(project, facts, hook="Eliminating documentation drift.")

    assert story.hook == "Eliminating documentation drift."
    assert len(story.key_claims) >= 1
    assert any("test" in c.claim.lower() for c in story.key_claims)


def test_collect_facts_nested_tests_and_evidence(tmp_path: Path):
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

    ledger = collect_facts(tmp_path, entrypoints=[])

    # Tests from nested dir
    assert ledger.get_fact("test_count").value == 2
    # Description
    assert ledger.get_fact("project_description").value == "Arrhythmia detection from wearable ECG signals"
    # Evidence metrics
    assert ledger.get_fact("metric_accuracy").value == 0.985
    assert ledger.get_fact("metric_latency_ms").value == 14.2


def test_story_builder_grounded_in_project_description(tmp_path: Path):
    """Verifies that build_story adapts to the domain instead of hardcoding self-referential text."""
    (tmp_path / "pyproject.toml").write_text("""[project]
name = "car-triage"
description = "Explainable collision damage triage"
version = "1.0.0"
""", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ready')", encoding="utf-8")

    project = detect_project(tmp_path)
    story = build_story(project, collect_facts(tmp_path, project.entrypoints))

    # Story problem and solution must mention the actual domain, NOT documentation drift!
    assert "explainable collision damage triage" in story.solution.lower()
    assert "documentation pipelines" not in story.problem.lower()
    assert "opaque estimates" in story.problem.lower()


def test_collect_facts_counts_code_under_dotted_parent_dir(tmp_path: Path):
    """A repo living under a dot-directory (e.g. ~/.projects) must still be counted."""
    repo = tmp_path / ".projects" / "tip-splitter"
    repo.mkdir(parents=True)
    (repo / "cli.py").write_text("print('hi')\nprint('bye')\n", encoding="utf-8")

    ledger = collect_facts(repo, entrypoints=[])

    assert ledger.get_fact("python_loc").value == 2
    assert ledger.get_fact("python_loc").source_file == "."


def test_collect_facts_counts_node_test_cases_not_files(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "habit-streak", "version": "1.0.0"}', encoding="utf-8")
    (tmp_path / "streak.test.js").write_text('test("a", () => {});\ntest("b", () => {});\n', encoding="utf-8")

    ledger = collect_facts(tmp_path, entrypoints=[])

    assert ledger.get_fact("test_count").value == 2


def test_architecture_nodes_do_not_invent_a_domain(tmp_path: Path):
    """A plain data/ folder must not become 'Pricing Storage' or similar invented claims."""
    (tmp_path / "cli.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "data").mkdir()

    labels = [n.label for n in detect_project(tmp_path).architecture_nodes]

    assert "Data Files" in labels
    assert not any("Pricing" in label for label in labels)


def test_refresh_story_keeps_edits_and_updates_numbers():
    from agentic_readme.models import ClaimItem, FactsLedger, StorySpec
    from agentic_readme.ground.story import refresh_story

    story = StorySpec(
        repo_name="demo", target_audience="Students", hook="My hand-written hook.",
        problem="p", solution="s",
        key_claims=[
            ClaimItem(claim="48 passing tests, not 480.", evidence_file="tests", metrics={"test_count": 48}),
            ClaimItem(claim="3800 lines of code.", evidence_file="src/", metrics={"loc": 3800}),
        ],
    )
    ledger = FactsLedger(repo_name="demo")
    ledger.add_fact("test_count", 53, "tests")
    ledger.add_fact("python_loc", 3900, "src/")

    out = refresh_story(story, ledger)
    assert out.hook == "My hand-written hook." and out.target_audience == "Students"
    assert out.key_claims[0].claim == "53 passing tests, not 480."
    assert out.key_claims[0].metrics == {"test_count": 53}
    assert out.key_claims[1].claim == "3900 lines of code." and out.key_claims[1].metrics == {"loc": 3900}
    assert refresh_story(story, ledger, hook="New hook.").hook == "New hook."


def test_evidence_metrics_found_under_dotted_parent_dir(tmp_path: Path):
    """Benchmark files must still count when the repo itself lives under a dot-directory."""
    repo = tmp_path / ".projects" / "bench"
    (repo / "data").mkdir(parents=True)
    (repo / "data" / "results.json").write_text('{"accuracy": 0.91}', encoding="utf-8")

    ledger = collect_facts(repo, entrypoints=[])

    assert ledger.get_fact("metric_accuracy").value == 0.91


def test_src_package_cli_is_found_as_entrypoint(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "tool"\n', encoding="utf-8")
    (tmp_path / "src" / "tool").mkdir(parents=True)
    (tmp_path / "src" / "tool" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "tool" / "cli.py").write_text("print('hi')\n", encoding="utf-8")

    assert detect_project(tmp_path).entrypoints == ["src/tool/cli.py"]
