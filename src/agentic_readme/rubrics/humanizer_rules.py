"""Humanizer rules and AI slop detection patterns based on Wikipedia's Signs of AI writing.

Used by the Voice Editor in Phase 2 to strip out generic LLM marketing fluff,
filler copulas, and false enthusiasm.
"""

from typing import List, Tuple

# Common AI buzzwords and hyperbolic intensifiers
AI_BUZZWORDS: List[str] = [
    "revolutionary",
    "delve",
    "delving",
    "testament",
    "tapestry",
    "seamless",
    "seamlessly",
    "beacon",
    "game-changer",
    "game changing",
    "unleash",
    "unleashing",
    "elevate",
    "elevating",
    "robust",
    "cutting-edge",
    "cutting edge",
    "paramount",
    "pivotal",
    "paradigm shift",
    "harness",
    "harnessing",
    "supercharge",
    "supercharged",
    "groundbreaking",
    "transformative",
    "comprehensive suite",
    "agonizing uncertainty",  # specific ClaimLens anti-pattern
]

# AI throat-clearing / formulaic transition patterns
AI_THROAT_CLEARING: List[str] = [
    "In today's fast-paced world",
    "In the modern era",
    "It is important to remember",
    "It's worth noting that",
    "At its core",
    "Look no further",
    "Without further ado",
    "In conclusion",
    "To sum up",
]

# Generic template greetings and emoji clutter
TEMPLATE_SLOP: List[str] = [
    "Welcome to",
    "Hey there",
    "Maintained? yes",
    "Happy coding",
]
