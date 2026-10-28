"""House-style rules: every word list, pattern and limit the checks use, in one place.

Edit this file to change what verify flags. The checks that use these lists live in
verify/claims.py (jargon), verify/voice.py (wording, badges, sections) and
verify/rendering.py (size limits).
"""

import re

# --- badges ----------------------------------------------------------------------------

PREFERRED_BADGE_STYLE = "flat-square"
FORBIDDEN_BADGE_STYLES = ["for-the-badge"]
MAX_BADGE_COUNT = 6  # more than this is visual noise

# --- media size limits -----------------------------------------------------------------

MAX_HERO_GIF_BYTES = 5 * 1024 * 1024      # recommended ceiling for a README GIF
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024   # GitHub's upload limit

# --- sections every README should have (regex, description) ----------------------------

REQUIRED_SECTIONS = [
    (r'<h1\s+align=["\']center["\']>', "Centered <h1> title header"),
    (r'(?:<p\s+align=["\']center["\']>\s*<em>|\*[\w\s,–—\'-]+\*)', "Italic 1-line hook"),
    (r'##\s+Quickstart', "Quickstart section"),
    (r'##\s+Evidence', "Evidence & Ground Truth section"),
    (r'##\s+Deliberately not included', "Deliberately not included tradeoff notes"),
]

# --- wording ---------------------------------------------------------------------------

# Phrases banned by the house style.
FORBIDDEN_PHRASES = [
    "Welcome to",
    "Maintained? yes",
    "⭐ Star us on GitHub",
    "Star us on GitHub",
    "Feel free to contribute",
    "Don't hesitate to",
    "In this repository, we",
    "GPU-accelerated SVG instrumentation",
    "Lab-grade figure mounting",
]

# Inflated marketing words, from Wikipedia's "Signs of AI writing".
AI_BUZZWORDS = [
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
    "agonizing uncertainty",  # seen in a real README
]

# Filler openers that add nothing.
AI_THROAT_CLEARING = [
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

# Template greetings.
TEMPLATE_SLOP = [
    "Welcome to",
    "Hey there",
    "Maintained? yes",
    "Happy coding",
]

# What the auto-fixer deletes outright (in addition to filler and forbidden phrases).
SLOP_TO_STRIP = [
    "Welcome to ",
    "Hey there! ",
    "Happy coding! ",
    "⭐ Star us on GitHub",
    "Star us on GitHub",
    "Feel free to contribute",
]

# --- leaked internal jargon ------------------------------------------------------------

# Internal notes that leaked into real public READMEs ("Option C Architecture", "Blueprint §11").
INTERNAL_JARGON_PATTERNS = [
    re.compile(r"\bOption\s+[A-Z]\s+Architecture\b", re.IGNORECASE),
    re.compile(r"\bBlueprint\s+§\s*\d+(?:/\s*§?\s*\d+)?\b", re.IGNORECASE),
    re.compile(r"\bPRD\s+§?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bRFC\s+§?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bSpec\s+§\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bSprint\s+\d+\s+Deliverable\b", re.IGNORECASE),
    re.compile(r"\bJira\s+[A-Z]+-\d+\b", re.IGNORECASE),
    re.compile(r"localhost:\d{4,5}", re.IGNORECASE),
    re.compile(r"127\.0\.0\.1:\d{4,5}", re.IGNORECASE),
    re.compile(r"\bTODO:\s*(?:fix|implement|cleanup|remove)\b", re.IGNORECASE),
]
