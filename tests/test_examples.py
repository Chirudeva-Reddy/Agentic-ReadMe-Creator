"""Regenerating each committed example must reproduce its README and assets byte for byte.

This pins the pipeline's behaviour: a refactor that changes any output fails here.
"""

import shutil
from pathlib import Path

import pytest

from agentic_readme import pipeline
from agentic_readme.models import FactsLedger

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
GENERATED_FILES = [
    "README.md",
    "assets/diagrams/architecture.excalidraw",
    "assets/diagrams/architecture.svg",
    "assets/diagrams/architecture-dark.svg",
    "assets/diagrams/architecture-static.svg",
    "assets/demo/demo.tape",
    "assets/demo/hero-demo.svg",
    "assets/demo/hero-demo-static.svg",
    "assets/video/brag_spec.json",
    "assets/video/scenes.md",
]


@pytest.mark.parametrize("name", ["tip-splitter", "habit-streak", "csv-dedupe"])
def test_example_regenerates_byte_for_byte(name: str, tmp_path: Path):
    committed = EXAMPLES / name
    project = tmp_path / name
    shutil.copytree(committed, project)

    result = pipeline.run(project)

    assert result["passed"]
    for relative in GENERATED_FILES:
        assert (project / relative).read_bytes() == (committed / relative).read_bytes(), relative
    expected_facts = FactsLedger.load(committed / ".agentic-readme" / "facts.json")
    assert {k: f.value for k, f in result["facts"].facts.items()} == {k: f.value for k, f in expected_facts.facts.items()}
