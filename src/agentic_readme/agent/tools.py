"""The agent's tools: everything the LLM is allowed to do, and nothing more.

make_tools(repo) returns six LangChain tools. Each is a small wrapper around deterministic
code in pipeline.py. The LLM chooses which tool to call and with which arguments.
LangChain turns each function's name, arguments and docstring into the tool description
the model reads, so the docstrings below are written for the model.

The guardrails are here, in code the model can't change:
  - list_files and read_file only see files inside the repo
  - update_story can change the story's words, never its claims or numbers
  - update_story and edit_readme reject any number that isn't in facts.json
  - no tool can write facts.json
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool
from langgraph.types import interrupt

from agentic_readme import pipeline
from agentic_readme.models import FactsLedger

MAX_READ_CHARS = 20_000
MAX_LISTED_FILES = 300
SKIPPED_FOLDERS = {"node_modules", "venv", "__pycache__", "build", "dist", "target"}

# A number on its own: "3", "3.11", "0.1.0" (but not the 2 inside "csv2json").
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)*(?!\w)")


def unknown_numbers(text: str, facts: FactsLedger, already_there: str = "") -> list[str]:
    """Numbers in `text` that appear neither in facts.json nor in `already_there`.

    ponytail: this also blocks harmless numbers ("24/7", "2 steps"); the model rephrases
    them in words, which costs nothing and keeps the rule simple.
    """
    allowed = set(NUMBER.findall(already_there))
    for fact in facts.facts.values():
        allowed.update(NUMBER.findall(str(fact.value)))
    return [n for n in NUMBER.findall(text) if n not in allowed]


def make_tools(repo: Path, review: bool = False) -> list:
    """Build the tools for one repo. Each tool remembers `repo`, so the model never passes paths outside it."""
    repo = Path(repo).resolve()

    def inside_repo(path: str) -> Path | None:
        target = (repo / path).resolve()
        if target == repo or repo in target.parents:
            return target
        return None

    @tool
    def list_files(folder: str = ".") -> str:
        """List the files in a folder of the repository, as paths relative to the repo root.

        Hidden folders, dependencies and build output are skipped.
        """
        start = inside_repo(folder)
        if start is None or not start.is_dir():
            return f"Error: {folder!r} is not a folder inside the repository."
        files = []
        for path in sorted(start.rglob("*")):
            parts = path.relative_to(repo).parts
            if path.is_file() and not any(p.startswith(".") or p in SKIPPED_FOLDERS for p in parts):
                files.append(str(path.relative_to(repo)))
        if len(files) > MAX_LISTED_FILES:
            return "\n".join(files[:MAX_LISTED_FILES]) + f"\n... and {len(files) - MAX_LISTED_FILES} more"
        return "\n".join(files) or "(no files)"

    @tool
    def read_file(path: str) -> str:
        """Read a text file from the repository, e.g. the entrypoint, sample data, tests, or .agentic-readme/story.yaml."""
        target = inside_repo(path)
        if target is None or not target.is_file():
            return f"Error: {path!r} is not a file inside the repository."
        data = target.read_bytes()
        if b"\x00" in data[:1024]:
            return f"{path} is a binary file; it can't be shown as text."
        text = data.decode("utf-8", errors="ignore")
        if len(text) > MAX_READ_CHARS:
            return text[:MAX_READ_CHARS] + f"\n... (cut at {MAX_READ_CHARS} characters)"
        return text

    @tool
    def update_story(
        hook: str | None = None,
        problem: str | None = None,
        solution: str | None = None,
        target_audience: str | None = None,
    ) -> str:
        """Rewrite the words of story.yaml, which the README is generated from. Pass only the fields to change.

        hook: one sentence naming a problem a stranger already has (the README tagline and the video's first line).
        problem: what is painful today, concretely.
        solution: what this project does about it.
        target_audience: who the README is for.
        Claims and numbers are not editable: they come from facts.json. Any number you write must already be in facts.json.
        """
        story, facts = pipeline.load_contracts(repo)
        if story is None or facts is None:
            return "Error: story.yaml or facts.json is missing."
        changes = {"hook": hook, "problem": problem, "solution": solution, "target_audience": target_audience}
        changes = {field: text for field, text in changes.items() if text is not None}
        if not changes:
            return "Nothing changed: pass at least one of hook, problem, solution, target_audience."

        for field, text in changes.items():
            invented = unknown_numbers(text, facts, already_there=getattr(story, field))
            if invented:
                return (f"Rejected: {field} contains {', '.join(invented)}, which isn't in facts.json. "
                        f"Use only numbers from facts.json, or say it in words. Nothing was saved.")

        story.model_copy(update=changes).save(pipeline.contract_path(repo, "story.yaml"))
        return f"Saved {', '.join(changes)} to story.yaml. Call produce_readme to rebuild the README."

    @tool
    def produce_readme() -> str:
        """Write README.md, the architecture diagrams, the terminal demo and the video storyboard from story.yaml and facts.json.

        This overwrites README.md, so make any edit_readme changes after it, not before.
        """
        story, facts = pipeline.load_contracts(repo)
        if story is None or facts is None:
            return "Error: story.yaml or facts.json is missing."
        if review:
            # Human-in-the-loop: pause the whole graph here until a person answers.
            answer = interrupt({
                "question": "Approve story.yaml before the README is written? Answer 'yes', or say what to change.",
                "story": pipeline.contract_path(repo, "story.yaml").read_text(encoding="utf-8"),
            })
            if str(answer).strip().lower() not in ("y", "yes"):
                return (f"The reviewer did not approve the story. Their feedback: {answer}\n"
                        f"Revise it with update_story, then call produce_readme again.")
        assets = pipeline.produce(story, facts, repo)
        written = [assets["readme"], *assets["diagrams"].values(), *assets["demo"].values(),
                   assets["video"]["spec_file"], assets["video"]["scene_table"]]
        return "Wrote:\n" + "\n".join(str(Path(p).relative_to(repo)) for p in written)

    @tool
    def verify_readme() -> str:
        """Check README.md and the generated assets against facts.json and GitHub's rendering rules.

        Problems with one right answer (a wrong badge number, a noisy badge style) are fixed automatically.
        Returns PASSED or FAILED, then every remaining finding with how to fix it.
        """
        _story, facts = pipeline.load_contracts(repo)
        if facts is None:
            return "Error: facts.json is missing."
        report, passed = pipeline.verify(repo, facts)
        summary = (f"{'PASSED' if passed else 'FAILED'}: {report.facts_checked} facts checked, "
                   f"{report.fatal_count} fatal, {report.warning_count} warnings, {report.minor_count} minor.")
        return "\n".join([summary, *report.finding_lines()])

    @tool
    def edit_readme(old_text: str, new_text: str) -> str:
        """Replace one exact piece of README.md with new text, to fix a finding from verify_readme.

        old_text must appear exactly once in README.md (copy it exactly; add surrounding words if it repeats).
        Any new number in new_text must already be in facts.json.
        """
        readme = repo / "README.md"
        if not readme.exists():
            return "Error: README.md doesn't exist yet. Call produce_readme first."
        text = readme.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count != 1:
            return f"Error: old_text appears {count} times in README.md; it must appear exactly once."
        _story, facts = pipeline.load_contracts(repo)
        invented = unknown_numbers(new_text, facts, already_there=old_text)
        if invented:
            return (f"Rejected: new_text contains {', '.join(invented)}, which isn't in facts.json. "
                    f"Use only numbers from facts.json, or say it in words. Nothing was changed.")
        readme.write_text(text.replace(old_text, new_text), encoding="utf-8")
        return "Edited README.md. Call verify_readme to check it."

    return [list_files, read_file, update_story, produce_readme, verify_readme, edit_readme]
