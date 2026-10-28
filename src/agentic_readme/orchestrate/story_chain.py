"""LangChain chain that rewrites the story's prose (hook, problem, solution) with Claude.

The chain only changes wording. Claims, metrics, and quickstart commands stay as grounding
wrote them, and a rewrite is thrown away if it mentions a number that is not in facts.json
or uses a word the Voice Editor would flag.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Set, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from agentic_readme.core.models import FactsLedger, StorySpec
from agentic_readme.core.observability import traced
from agentic_readme.rubrics.humanizer_rules import AI_BUZZWORDS


class StoryProse(BaseModel):
    """The three story fields the model is allowed to rewrite."""
    hook: str = Field(description="One sentence: the reader's problem, then what the project does about it.")
    problem: str = Field(description="At most two sentences on what goes wrong without this project.")
    solution: str = Field(description="At most two sentences on what the project does, in plain words.")


SYSTEM_PROMPT = """You edit the opening lines of a README so a first-time visitor understands what the project does and why it matters.

Rewrite the hook, problem, and solution. Use only the facts listed and the current draft: do not add numbers, versions, names, or features that appear in neither. Write plain sentences without exclamation marks, and avoid these words: {banned_words}."""

HUMAN_PROMPT = """Project: {repo_name}
Audience: {audience}

Facts from facts.json:
{facts}

Current draft:
hook: {hook}
problem: {problem}
solution: {solution}"""

STORY_PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])

_NUMBER = re.compile(r"\d+(?:\.\d+)*")


def build_story_chain(llm: Any) -> Runnable:
    """prompt | chat model with structured output, returning a StoryProse."""
    return STORY_PROMPT | llm.with_structured_output(StoryProse, method="json_schema")


def chain_inputs(story: StorySpec, ledger: FactsLedger) -> dict:
    facts = "\n".join(f"- {key}: {fact.value}" for key, fact in sorted(ledger.facts.items()))
    return {
        "banned_words": ", ".join(AI_BUZZWORDS),
        "repo_name": story.repo_name,
        "audience": story.target_audience,
        "facts": facts,
        "hook": story.hook,
        "problem": story.problem,
        "solution": story.solution,
    }


def ungrounded_numbers(text: str, story: StorySpec, ledger: FactsLedger) -> Set[str]:
    """Numbers in `text` that appear neither in a fact value nor in the current draft."""
    allowed: Set[str] = set()
    for fact in ledger.facts.values():
        allowed.update(_NUMBER.findall(str(fact.value)))
    allowed.update(_NUMBER.findall(" ".join([story.hook, story.problem, story.solution])))
    return set(_NUMBER.findall(text)) - allowed


def flagged_words(text: str) -> Set[str]:
    return {w for w in AI_BUZZWORDS if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE)}


@traced("polish_story")
def polish_story(
    story: StorySpec,
    ledger: FactsLedger,
    llm: Optional[Any] = None,
    chain: Optional[Runnable] = None,
) -> Tuple[StorySpec, str]:
    """Rewrite the story's prose. Returns (story, note); a rejected rewrite returns the input story."""
    if chain is None:
        if llm is None:
            from agentic_readme.orchestrate.llm import default_chat_model
            llm = default_chat_model()
        chain = build_story_chain(llm)

    try:
        prose = chain.invoke(chain_inputs(story, ledger))
    except Exception as exc:  # no credentials, refusal, network, unparseable output
        return story, f"kept the grounded story: model call failed ({exc.__class__.__name__}: {exc})"

    text = " ".join([prose.hook, prose.problem, prose.solution])
    numbers = ungrounded_numbers(text, story, ledger)
    if numbers:
        return story, f"kept the grounded story: rewrite added numbers not in facts.json ({', '.join(sorted(numbers))})"
    words = flagged_words(text)
    if words:
        return story, f"kept the grounded story: rewrite used flagged words ({', '.join(sorted(words))})"

    polished = story.model_copy(update={"hook": prose.hook, "problem": prose.problem, "solution": prose.solution})
    return polished, "rewrote hook, problem, and solution"
