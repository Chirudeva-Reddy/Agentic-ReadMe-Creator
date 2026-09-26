"""Tests for Phase 2 Claim Auditor: Fact drift and jargon leakage detection."""

from pathlib import Path
from agentic_readme.core.models import (
    FactsLedger,
    FactSourceType,
    FindingCategory,
    FindingSeverity,
    VerificationReport,
)
from agentic_readme.verify.claim_auditor import ClaimAuditor


def test_claim_auditor_catches_claimlens_52_vs_44_test_drift(tmp_path: Path):
    """Recreate and catch the exact ClaimLens bug:

    Badge states '52 passed', while body text states '44 tests' or
    ledger records 52 tests passed.
    """
    ledger = FactsLedger(repo_name="ClaimLens")
    ledger.add_fact(
        key="test_count",
        value=52,
        source_file="tests/",
        source_type=FactSourceType.TEST_RUN,
        description="52 passing pytest cases",
    )

    # README with drifted text: badge has 52, but text says 44 tests passed!
    drifted_readme = tmp_path / "README.md"
    drifted_readme.write_text("""# ClaimLens
[![Tests](https://img.shields.io/badge/tests-52%20passed-success.svg)](tests/)

## Quickstart
Run the test suite across 44 tests to verify triage.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(drifted_readme)

    # Must flag the 44 tests drift!
    drift_findings = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT]
    assert len(drift_findings) >= 1
    assert any("44" in f.actual for f in drift_findings)
    assert any("52" in f.expected for f in drift_findings)
    assert report.passed is False


def test_claim_auditor_catches_badge_drift(tmp_path: Path):
    """When badge claims 60 tests but ledger has 52 tests."""
    ledger = FactsLedger(repo_name="ClaimLens")
    ledger.add_fact("test_count", 52, "tests/", FactSourceType.TEST_RUN)

    readme = tmp_path / "README.md"
    readme.write_text("""# ClaimLens
[![Tests](https://img.shields.io/badge/tests-60%20passed-success.svg)](tests/)
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    drift_findings = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT]
    assert len(drift_findings) == 1
    assert drift_findings[0].actual == "60"
    assert drift_findings[0].expected == "52"


def test_claim_auditor_catches_internal_jargon_leakage(tmp_path: Path):
    """Catches internal development artifacts leaking into public READMEs:

    - 'Option C Architecture' (ClaimLens real bug)
    - 'Blueprint §11/§13' (ClaimLens real bug)
    - 'localhost:8000'
    """
    ledger = FactsLedger(repo_name="ClaimLens")
    readme = tmp_path / "README.md"
    readme.write_text("""# ClaimLens
> Option C Architecture: Two-Stage Computer Vision + Scraped UAE OEM Parts.
Refer to Blueprint §11/§13 for the implementation details.
Visit localhost:8000 to view dashboard.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    jargon_findings = [f for f in report.findings if f.category == FindingCategory.JARGON_LEAKAGE]
    assert len(jargon_findings) >= 3

    jargon_texts = [f.actual for f in jargon_findings]
    assert any("Option C Architecture" in j for j in jargon_texts)
    assert any("Blueprint §11/§13" in j for j in jargon_texts)
    assert any("localhost:8000" in j for j in jargon_texts)


def test_claim_auditor_passes_clean_readme(tmp_path: Path):
    ledger = FactsLedger(repo_name="verified-repo")
    ledger.add_fact("test_count", 52, "tests/", FactSourceType.TEST_RUN)
    ledger.add_fact("license", "MIT", "LICENSE", FactSourceType.SOURCE_CODE)

    # Create tests/ and LICENSE so badge evidence links pass
    (tmp_path / "tests").mkdir()
    (tmp_path / "LICENSE").write_text("MIT", encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text("""# verified-repo
<a href="tests/"><img alt="tests 52 passed" src="https://img.shields.io/badge/tests-52%20passed-success.svg"></a>
<a href="LICENSE"><img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>

Our suite includes 52 tests verifying system functionality.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)
    assert report.fatal_count == 0
    assert report.passed is True


def test_claim_auditor_catches_small_repo_test_drift(tmp_path: Path):
    """Proves fix for the boundary bug where repos with <= 5 tests silently ignored drift."""
    ledger = FactsLedger(repo_name="small-repo")
    ledger.add_fact("test_count", 3, "tests/", FactSourceType.TEST_RUN)

    readme = tmp_path / "README.md"
    readme.write_text("""# small-repo
We run 4 tests to ensure system stability.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)
    findings = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT]
    assert len(findings) == 1
    assert findings[0].actual == "4"
    assert findings[0].expected == "3"


def test_claim_auditor_catches_cross_asset_drift(tmp_path: Path):
    """Cross-asset auditing across /brag video spec, demo tape, and Excalidraw."""
    ledger = FactsLedger(repo_name="multi-asset")
    ledger.add_fact("test_count", 52, "tests/", FactSourceType.TEST_RUN)

    # Create video spec with drifted test count and leaked jargon
    video_dir = tmp_path / "assets" / "video"
    video_dir.mkdir(parents=True)
    brag_spec = video_dir / "brag_spec.json"
    brag_spec.write_text("""{
        "title": "Launch",
        "scenes": [
            {"timecode": "00:00", "narration": "Option C Architecture verified across 44 tests."}
        ]
    }""", encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text("# multi-asset\nVerified across 52 tests.\n", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    # Should catch test drift in video spec (44 vs 52)
    video_drifts = [f for f in report.findings if f.location == "assets/video/brag_spec.json" and f.category == FindingCategory.FACT_DRIFT]
    assert len(video_drifts) >= 1
    assert video_drifts[0].actual == "44"

    # Should catch leaked jargon in video spec
    video_jargons = [f for f in report.findings if f.location == "assets/video/brag_spec.json" and f.category == FindingCategory.JARGON_LEAKAGE]
    assert len(video_jargons) >= 1
    assert "Option C Architecture" in video_jargons[0].actual


def test_claim_auditor_catches_benchmark_metric_drift(tmp_path: Path):
    """Verifies that numeric benchmark assertions in text are checked against facts.json."""
    ledger = FactsLedger(repo_name="bench-repo")
    ledger.add_fact("metric_accuracy", 0.94, "data/results.json", FactSourceType.BENCHMARK)

    readme = tmp_path / "README.md"
    readme.write_text("""# bench-repo
Our model achieves accuracy of 0.50 on the benchmark.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    metric_findings = [f for f in report.findings if "accuracy" in f.message.lower()]
    assert len(metric_findings) >= 1
    assert metric_findings[0].actual == "0.5"
    assert metric_findings[0].expected == "0.94"


def test_claim_auditor_catches_broken_badge_evidence_links(tmp_path: Path):
    """Flags badges linking to files that don't exist in the repository."""
    ledger = FactsLedger(repo_name="badge-repo")
    readme = tmp_path / "README.md"
    readme.write_text("""# badge-repo
<a href="nonexistent/evidence.json"><img src="https://img.shields.io/badge/eval-passed-green" alt="eval"></a>
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    broken = [f for f in report.findings if "missing evidence target" in f.message.lower()]
    assert len(broken) == 1
    assert "nonexistent/evidence.json" in broken[0].actual


def test_claim_auditor_catches_loc_drift(tmp_path: Path):
    """Verifies that LOC discrepancies between README and FactsLedger are caught."""
    ledger = FactsLedger(repo_name="loc-repo")
    ledger.add_fact("python_loc", 4106, "src/", FactSourceType.SOURCE_CODE)

    readme = tmp_path / "README.md"
    readme.write_text("""# loc-repo
Modular architecture spanning 3709 lines of code across pipeline stages.

| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
| Modular architecture | `loc: 3709` | `src/` | ✅ Verified |
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    loc_findings = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT and "lines of code" in f.message.lower() or "loc" in f.message.lower()]
    assert len(loc_findings) >= 1
    assert any("3709" in f.actual for f in loc_findings)
    assert any("4106" in f.expected for f in loc_findings)
    assert report.passed is False


def test_claim_auditor_catches_evidence_table_drift(tmp_path: Path):
    """Flags ungrounded metrics and mismatched values in the Evidence table."""
    ledger = FactsLedger(repo_name="evidence-repo")
    ledger.add_fact("test_count", 50, "tests/", FactSourceType.TEST_RUN)
    ledger.add_fact("protocol", "2024-11-05", "mcp.json", FactSourceType.CONFIG)

    # Table claims 60 tests and an ungrounded metric `unknown_metric: 123`
    readme = tmp_path / "README.md"
    readme.write_text("""# evidence-repo
| Claim | Verified Metric | Source Evidence | Status |
| :--- | :--- | :--- | :--- |
| Test suite | `test_count: 60` | `tests/` | ✅ Verified |
| Unknown metric | `unknown_metric: 123` | `data.json` | ✅ Verified |
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)

    findings = [f for f in report.findings if f.category == FindingCategory.FACT_DRIFT]
    # Mismatched test_count
    assert any("60" in (f.actual or "") for f in findings)
    # Ungrounded unknown_metric
    assert any("unknown_metric" in f.message for f in findings)

