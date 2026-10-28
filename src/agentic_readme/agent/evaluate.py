"""Score the agent on the example projects, as a LangSmith experiment.

run_eval() does three things:
  1. makes sure a LangSmith dataset exists, with one row per folder in examples/
  2. for each row, copies that project to a temp folder, deletes its README and story.yaml
     (so the agent starts from scratch), and runs the agent on the copy
  3. scores each run with deterministic graders, so no LLM judges another LLM:
       verify_passed           did the final check pass?
       fatal_findings          how many fatal findings a fresh audit still reports (want 0)
       checks_used             how many final checks the agent needed (fewer is better)
       story_numbers_grounded  is every number in the story's words also in facts.json?

Each run is traced, so in LangSmith you can open a low score and read the exact tool calls.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langsmith import Client

from agentic_readme import pipeline
from agentic_readme.agent.graph import run_agent
from agentic_readme.agent.tools import unknown_numbers

DATASET = "agentic-readme-examples"


def run_on_copy(project_dir: Path, model: str | BaseChatModel | None = None) -> dict:
    """Run the agent on a fresh copy of one example and measure the result."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / project_dir.name
        shutil.copytree(project_dir, project)
        (project / "README.md").unlink(missing_ok=True)
        (project / ".agentic-readme" / "story.yaml").unlink(missing_ok=True)

        result = run_agent(project, model)

        story, facts = pipeline.load_contracts(project)
        readme = project / "README.md"
        fatal = pipeline.check(readme, facts).fatal_count if readme.exists() else 1
        words = " ".join([story.hook, story.problem, story.solution, story.target_audience])
        return {
            "passed": result["passed"],
            "fatal_findings": fatal,
            "checks_used": result["checks"],
            "tool_calls": result["tool_calls"],
            "hook": story.hook,
            "invented_numbers": unknown_numbers(words, facts),
        }


# --- graders: LangSmith passes each run's outputs dict to these -------------------------

def verify_passed(outputs: dict) -> bool:
    return outputs["passed"]


def fatal_findings(outputs: dict) -> int:
    return outputs["fatal_findings"]


def checks_used(outputs: dict) -> int:
    return outputs["checks_used"]


def story_numbers_grounded(outputs: dict) -> bool:
    return not outputs["invented_numbers"]


GRADERS = [verify_passed, fatal_findings, checks_used, story_numbers_grounded]


def run_eval(examples_dir: Path = Path("examples"), model: str | None = None) -> dict:
    """Run the experiment; returns its name and LangSmith URL."""
    examples_dir = Path(examples_dir).resolve()
    projects = sorted(p.name for p in examples_dir.iterdir() if (p / ".agentic-readme").is_dir())

    client = Client()
    if not client.has_dataset(dataset_name=DATASET):
        dataset = client.create_dataset(DATASET, description="Example projects the README agent is scored on.")
        client.create_examples(dataset_id=dataset.id, examples=[{"inputs": {"project": name}} for name in projects])

    def target(inputs: dict) -> dict:
        return run_on_copy(examples_dir / inputs["project"], model)

    results = client.evaluate(
        target,
        data=DATASET,
        evaluators=GRADERS,
        experiment_prefix=f"agentic-readme-{model or 'default'}",
        metadata={"model": model or "default"},
        max_concurrency=1,
    )
    return {"experiment": results.experiment_name, "url": results.url}
