"""Patterns to detect leaked internal specification jargon in public documentation.

Identified from real repos like ClaimLens where internal working documents
(e.g., 'Option C Architecture', 'Blueprint §11/§13') accidentally leaked into public READMEs.
"""

import re
from typing import List, Pattern

# Regular expressions matching leaked internal development jargon
INTERNAL_JARGON_PATTERNS: List[Pattern] = [
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
