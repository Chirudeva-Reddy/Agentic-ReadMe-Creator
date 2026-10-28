"""Check every number in the README (and the other generated files) against facts.json.

check_claims(readme_path, facts) looks for:
  - fact drift: a badge or sentence whose number differs from facts.json
    (e.g. a badge saying 52 tests pass when facts.json records 44)
  - leaked internal jargon ("Option C Architecture", "localhost:8000", ...)
  - the same problems in the video storyboard, scene table, diagram and demo script
  - badges that link to a file that doesn't exist

Each check adds findings to the report; `facts_checked` counts what was compared.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_readme.models import FactsLedger, FindingCategory, FindingSeverity, VerificationReport
from agentic_readme.rules import INTERNAL_JARGON_PATTERNS

FATAL = FindingSeverity.FATAL
WARNING = FindingSeverity.WARNING


def check_claims(readme_path: Path, facts: FactsLedger, report: VerificationReport | None = None) -> VerificationReport:
    if report is None:
        report = VerificationReport()
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    name = readme_path.name
    project_dir = readme_path.parent

    _test_count(text, name, facts, report)
    _python_version(text, name, facts, report)
    _project_version(text, name, facts, report)
    _license(text, name, facts, report)
    _lines_of_code(text, name, facts, report)
    _evidence_table(text, name, facts, report)
    _benchmark_numbers(text, name, facts, report)
    _jargon(text, name, report)
    _other_assets(project_dir, facts, report)
    _badge_links(text, project_dir, report)
    return report


def _drift(report, message, location, expected, actual, fix=None, severity=FATAL) -> None:
    report.add_finding(FindingCategory.FACT_DRIFT, severity, message,
                       location=location, expected=expected, actual=actual, suggested_fix=fix)


def _test_count(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    """Badges like tests-52%20passed and sentences like "44 tests" must match test_count."""
    fact = facts.get_fact("test_count")
    if not fact:
        return
    expected = str(fact.value)
    report.facts_checked += 1

    for found in re.findall(r"(?:tests?|pytest)-(\d+)(?:%20|\s+|-)?(?:passed)?", text, re.IGNORECASE):
        if found != expected:
            _drift(report,
                   f"Test count badge drift: badge claims {found} tests passed, but facts ledger records {expected}.",
                   f"{name} (badge)", expected, found,
                   f"Update badge to reflect verified test count: tests-{expected}%20passed.")

    sentence = r"\b(\d+)\s+(?:passing\s+tests|tests\s+passed|tests|pytest\s+cases|unit\s+tests)\b"
    for found in re.findall(sentence, text, re.IGNORECASE):
        if found != expected:
            _drift(report,
                   f"Fact drift in text: claims {found} tests, while verified facts ledger has {expected} tests.",
                   f"{name} (body text)", expected, found,
                   f"Replace '{found} tests' with '{expected} tests' to preserve cross-asset consistency.")


def _python_version(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    fact = facts.get_fact("python_version")
    if not fact:
        return
    expected = str(fact.value)
    report.facts_checked += 1

    for found in re.findall(r"badge/python-([0-9\.\+\>\<=\^]+)", text, re.IGNORECASE):
        found = found.replace("%2B", "+").replace("%20", " ")
        if found not in expected and expected not in found:
            _drift(report,
                   f"Python version badge discrepancy: badge says {found}, ledger specifies {expected}.",
                   f"{name} (python badge)", expected, found,
                   f"Update badge to match pyproject.toml requirement ({expected}).", WARNING)


def _project_version(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    fact = facts.get_fact("project_version") or facts.get_fact("package_version") or facts.get_fact("cargo_version")
    if not fact:
        return
    expected = str(fact.value)
    report.facts_checked += 1

    for found in re.findall(r"badge/(?:version|release|v)-v?([0-9\.]+)", text, re.IGNORECASE):
        if found != expected:
            _drift(report,
                   f"Version badge discrepancy: badge says v{found}, ledger specifies {expected}.",
                   f"{name} (version badge)", expected, found,
                   f"Update badge to match project version ({expected}).", WARNING)


def _license(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    fact = facts.get_fact("license")
    if not fact:
        return
    expected = str(fact.value)
    report.facts_checked += 1

    # The badge value, without a colour suffix like -blue or a .svg ending.
    badge = (r"badge/licen[sc]e-([a-zA-Z0-9\.\_\-]+?)"
             r"(?:-(?:blue|green|orange|red|yellow|lightgrey|emerald|purple|[0-9a-fA-F]{6}))?"
             r"(?:\.svg)?(?:[?\"\'\s&]|$)")
    for found in re.findall(badge, text, re.IGNORECASE):
        found = found.replace("--", "-")
        if found.upper() != expected.upper():
            _drift(report,
                   f"License badge discrepancy: badge states {found}, actual LICENSE file is {expected}.",
                   f"{name} (license badge)", expected, found,
                   f"Align badge with repository license ({expected}).")


def _lines_of_code(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    fact = facts.get_fact("python_loc")
    if not fact:
        return
    expected = str(fact.value)
    report.facts_checked += 1

    for found in re.findall(r"\bloc:\s*(\d+)\b", text, re.IGNORECASE):  # evidence table: `loc: 3709`
        if found != expected:
            _drift(report,
                   f"Lines of code fact drift in evidence table: claims {found} LOC, ledger records {expected}.",
                   f"{name} (evidence table)", expected, found,
                   f"Update table metric to 'loc: {expected}'.")

    for found in re.findall(r"\b(\d+)\s+lines of code\b", text, re.IGNORECASE):
        if found != expected:
            _drift(report,
                   f"Lines of code fact drift in text: claims {found} lines of code, ledger records {expected}.",
                   f"{name} (body text)", expected, found,
                   f"Update '{found} lines of code' to '{expected} lines of code'.")


def _evidence_table(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    """Every `key: value` in the Evidence table must be a fact with that exact value."""
    row = r"\|\s*([^|]+?)\s*\|\s*`([^:`]+):\s*([^`]+)`\s*\|\s*\[?`?([^`\]|]+)`?\]?(?:\([^)]+\))?\s*\|\s*([^|]+)\|"
    for _claim, key, value, _evidence, _status in re.findall(row, text):
        key, value = key.strip(), value.strip()
        report.facts_checked += 1

        fact = facts.get_fact(key)
        if fact is None and key == "loc":
            fact = facts.get_fact("python_loc")
        if fact is None and key == "tests":
            fact = facts.get_fact("test_count")

        if fact is None:
            _drift(report,
                   f"Evidence table metric '{key}: {value}' is not registered in facts.json ledger.",
                   f"{name} (evidence table)", f"Registered fact in facts.json for '{key}'", f"{key}: {value}",
                   f"Register '{key}' in facts.json or extractor.", WARNING)
        elif value != str(fact.value).strip():
            expected = str(fact.value).strip()
            _drift(report,
                   f"Fact drift in evidence table for '{key}': table states '{value}', facts.json has '{expected}'.",
                   f"{name} (evidence table)", expected, value,
                   f"Update table metric to reflect ledger value ({expected}).")


def _benchmark_numbers(text: str, name: str, facts: FactsLedger, report: VerificationReport) -> None:
    """A number written near a benchmark's name must be within 10% of the recorded value."""
    for key, fact in facts.facts.items():
        report.facts_checked += 1
        if not key.startswith("metric_") or not isinstance(fact.value, (int, float)):
            continue
        metric = key.replace("metric_", "")
        actual = float(fact.value)
        nearby_number = re.compile(rf"\b{re.escape(metric)}\b[^\n\.\,]{{0,35}}(\d+(?:\.\d+)?)", re.IGNORECASE)
        for match in nearby_number.finditer(text):
            claimed = float(match.group(1))
            if actual > 0 and abs(claimed - actual) / actual > 0.10:
                _drift(report,
                       f"Metric discrepancy for '{metric}': claims {claimed}, ledger records {actual}.",
                       f"{name} (around index {match.start()})", str(actual), str(claimed),
                       f"Update '{metric}' in documentation to match ledger value ({actual}).", WARNING)


def _jargon(text: str, name: str, report: VerificationReport) -> None:
    """Internal sprint or spec notes must never reach a public README."""
    for pattern in INTERNAL_JARGON_PATTERNS:
        for match in pattern.finditer(text):
            found = match.group(0)
            report.add_finding(
                FindingCategory.JARGON_LEAKAGE, FATAL,
                f"Internal specification jargon leaked into public documentation: '{found}'.",
                location=f"{name} (around index {match.start()})",
                expected="Public user-facing description",
                actual=found,
                suggested_fix=f"Remove internal artifact reference '{found}' from public documentation.",
            )


# The other generated files: (path, what the message calls it, what was expected, fix).
OTHER_ASSETS = [
    ("assets/video/brag_spec.json", "Internal jargon leaked into /brag launch video spec",
     "Clean public launch narration", "Sanitize /brag launch video storyboard."),
    ("assets/video/scenes.md", "Internal jargon leaked into video scene table", "Clean scene table", None),
    ("assets/diagrams/architecture.excalidraw", "Internal jargon found in architecture diagram",
     "Clean architectural component label", None),
    ("assets/demo/demo.tape", "Internal jargon found in demo.tape", "Clean CLI commands", None),
]


def _other_assets(project_dir: Path, facts: FactsLedger, report: VerificationReport) -> None:
    """Scan the storyboard, scene table, diagram and demo script for jargon (and test-count drift)."""
    test_fact = facts.get_fact("test_count")
    expected_tests = str(test_fact.value) if test_fact else None

    for relative_path, message, expected, fix in OTHER_ASSETS:
        path = project_dir / relative_path
        if not path.exists():
            continue
        report.facts_checked += 1
        content = path.read_text(encoding="utf-8", errors="ignore")

        for pattern in INTERNAL_JARGON_PATTERNS:
            match = pattern.search(content)
            if match:
                report.add_finding(FindingCategory.JARGON_LEAKAGE, FATAL, f"{message}: '{match.group(0)}'.",
                                   location=relative_path, expected=expected, actual=match.group(0),
                                   suggested_fix=fix)

        # The video narration is read aloud, so its test count must be right too.
        if relative_path == "assets/video/brag_spec.json" and expected_tests:
            for found in re.findall(r"\b(\d+)\s+tests?\b", content, re.IGNORECASE):
                if found != expected_tests:
                    _drift(report,
                           f"Test count drift in /brag video spec: claims {found} tests, facts ledger has {expected_tests}.",
                           relative_path, expected_tests, found,
                           f"Synchronize video narration with facts ledger ({expected_tests} tests).")


def _badge_links(text: str, project_dir: Path, report: VerificationReport) -> None:
    """A badge must link to real evidence, so a relative link must point at an existing file."""
    badge = r'<a\s+href=["\']([^"\']+)["\']>\s*<img[^>]*badge[^>]*>\s*</a>'
    for match in re.finditer(badge, text, re.IGNORECASE):
        href = match.group(1).split("#")[0].strip()
        report.facts_checked += 1
        if not href or href.startswith(("http://", "https://")):
            continue
        if not (project_dir / href).resolve().exists():
            _drift(report,
                   f"Badge links to missing evidence target: '{href}'. Badges must link to real evidence.",
                   "README.md (badge link)", "Existing file or directory in repository", href,
                   "Update badge href to link to an existing evidence file or test directory.", WARNING)
