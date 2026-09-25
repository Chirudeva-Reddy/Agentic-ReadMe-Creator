"""Tests for Phase 2 Evaluator-Optimizer auto-fixing loop."""

from pathlib import Path
from agentic_readme.core.models import ArchitectureNode, ClaimItem, FactsLedger, FactSourceType, StorySpec
from agentic_readme.verify.optimizer import EvaluatorOptimizer


def test_optimizer_auto_fixes_drift_video_and_jargon(tmp_path: Path):
    ledger = FactsLedger(repo_name="demo-repo")
    ledger.add_fact("test_count", 52, "tests/", FactSourceType.TEST_RUN)
    ledger.add_fact("license", "MIT", "LICENSE", FactSourceType.SOURCE_CODE)

    story = StorySpec(
        repo_name="demo-repo",
        target_audience="Devs",
        hook="Fast triage.",
        problem="Opaque triage.",
        solution="Explainable triage.",
        key_claims=[ClaimItem(claim="52 passing tests", evidence_file="tests/")],
        architecture_nodes=[ArchitectureNode(id="core", label="Core Engine")],
    )

    readme = tmp_path / "README.md"
    readme.write_text("""# demo-repo
[![Tests](https://img.shields.io/badge/tests-44%20passed-blue.svg?style=for-the-badge)](tests/)

Option C Architecture details are here.
Run our suite of 44 passing tests.

<video src="assets/demo.mp4" poster="assets/poster.jpg">
</video>
""", encoding="utf-8")

    optimizer = EvaluatorOptimizer(tmp_path, ledger)
    report, passed = optimizer.run_loop(readme, story, max_rounds=2)

    fixed_content = readme.read_text(encoding="utf-8")

    # 1. Test count badge fixed to 52
    assert "tests-52%20passed" in fixed_content

    # 2. Test count body text fixed to 52 tests
    assert "52 tests" in fixed_content
    assert "44 passing tests" not in fixed_content

    # 3. Leaked jargon removed
    assert "Option C Architecture" not in fixed_content

    # 4. Relative video tag replaced with anchor preview
    assert "<video" not in fixed_content
    assert 'href="assets/demo.mp4"' in fixed_content
    assert 'src="assets/poster.jpg"' in fixed_content

    # 5. Badge style cleaned
    assert "style=flat-square" in fixed_content
    assert "style=for-the-badge" not in fixed_content
