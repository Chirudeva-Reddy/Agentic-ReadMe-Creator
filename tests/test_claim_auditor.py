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

    readme = tmp_path / "README.md"
    readme.write_text("""# verified-repo
[![Tests](https://img.shields.io/badge/tests-52%20passed-success.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Our suite includes 52 tests verifying system functionality.
""", encoding="utf-8")

    auditor = ClaimAuditor(ledger)
    report = auditor.audit(readme)
    assert report.fatal_count == 0
    assert report.passed is True
