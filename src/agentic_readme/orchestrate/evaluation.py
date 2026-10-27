"""LangSmith evaluation of the LangGraph pipeline over the committed examples.

Dataset: one row per examples/<name>/ that has a committed facts.json. The input is the
example's folder name; the reference output is the test count in that facts.json.
Target:  runs the graph on a temporary copy of the example, so the committed files are
         never touched, and returns what the verifier reported.
Evaluators score each run. run_local_evaluation() applies the same evaluators without
LangSmith, so the checks also work offline and in CI.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List

from rich.console import Console

from agentic_readme.core.models import FactsLedger, VerificationReport
from agentic_readme.core.runner import contract_path

DATASET_NAME = "agentic-readme-examples"


def build_examples(examples_dir: Path) -> List[Dict[str, Any]]:
    """Dataset rows in LangSmith's {"inputs", "outputs"} shape."""
    rows = []
    for facts_file in sorted(Path(examples_dir).glob("*/.agentic-readme/facts.json")):
        test_fact = FactsLedger.load(facts_file).get_fact("test_count")
        rows.append({
            "inputs": {"example": facts_file.parent.parent.name},
            "outputs": {"test_count": test_fact.value if test_fact else None},
        })
    return rows


def make_target(examples_dir: Path) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """The function under evaluation: example name in, verification summary out."""
    from agentic_readme.orchestrate.graph import run_graph

    def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
        source = Path(examples_dir) / inputs["example"]
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / source.name
            shutil.copytree(source, repo, ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache"))
            state = run_graph(repo, console=Console(stderr=True, quiet=True))
            test_fact = FactsLedger.load(contract_path(repo, "facts.json")).get_fact("test_count")

        report = VerificationReport.model_validate(state["report"])
        return {
            "passed": state["passed"],
            "rounds": state["round"],
            "facts_checked": report.facts_checked,
            "fatal_count": report.fatal_count,
            "warning_count": report.warning_count,
            "test_count": test_fact.value if test_fact else None,
        }

    return target


# Evaluators. LangSmith passes arguments by name, so each takes (outputs, reference_outputs).
# None start with "test_": pytest would collect them in any test module that imports them.

def verification_passed(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """No fatal findings: the README agrees with facts.json."""
    return {"key": "verification_passed", "score": bool(outputs["passed"])}


def first_pass_clean(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """The generated README needed no auto-fixes (clean on verify round 1)."""
    clean = outputs["rounds"] == 1 and outputs["fatal_count"] == 0 and outputs["warning_count"] == 0
    return {"key": "first_pass_clean", "score": clean}


def reproduces_test_count(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Grounding finds the same test count as the example's committed facts.json."""
    return {"key": "test_count_matches", "score": outputs["test_count"] == reference_outputs["test_count"]}


EVALUATORS = [verification_passed, first_pass_clean, reproduces_test_count]


def run_local_evaluation(examples_dir: Path) -> List[Dict[str, Any]]:
    """Run target and evaluators on every example without LangSmith."""
    target = make_target(examples_dir)
    results = []
    for row in build_examples(examples_dir):
        outputs = target(row["inputs"])
        scores = {}
        for evaluator in EVALUATORS:
            result = evaluator(outputs, row["outputs"])
            scores[result["key"]] = result["score"]
        results.append({"example": row["inputs"]["example"], "outputs": outputs, "scores": scores})
    return results


def run_langsmith_evaluation(examples_dir: Path, dataset_name: str = DATASET_NAME, experiment_prefix: str = "agentic-readme-graph"):
    """Create the dataset on first use, then run an experiment. Needs LANGSMITH_API_KEY."""
    from langsmith import Client

    client = Client()
    if not client.has_dataset(dataset_name=dataset_name):
        dataset = client.create_dataset(dataset_name, description="Committed agentic-readme examples and their test counts.")
        client.create_examples(dataset_id=dataset.id, examples=build_examples(examples_dir))

    return client.evaluate(
        make_target(examples_dir),
        data=dataset_name,
        evaluators=EVALUATORS,
        experiment_prefix=experiment_prefix,
        metadata={"pipeline": "langgraph"},
    )
