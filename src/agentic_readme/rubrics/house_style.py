"""House style rubric distilled from high-performing references (duet, body2health).

Defines structural and formatting constraints for the README.
"""

from typing import List

# Badge style preferred across house style
PREFERRED_BADGE_STYLE = "flat-square"
MAX_BADGE_COUNT = 6  # Avoid badge flood (NLP-Proj anti-pattern with 9+ noisy badges)

# Required structural elements
REQUIRED_SECTIONS = [
    "header_centered",
    "italic_hook",
    "badges_with_evidence",
    "hero_asset",
    "architecture_picture",
    "evidence_grounding",
    "quickstart",
    "deliberate_omissions",
]

# Anti-patterns strictly forbidden by house style
FORBIDDEN_PHRASES = [
    "Welcome to",
    "Maintained? yes",
    "⭐ Star us on GitHub",
    "Feel free to contribute",
    "Don't hesitate to",
    "In this repository, we",
]
