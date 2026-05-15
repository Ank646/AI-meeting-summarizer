"""
Extraction utilities:
  - Temporal normalization (deadline text → ISO datetime)
  - Dependency detection (task dependency phrases)
  - Assignee extraction heuristics
"""

import re
from datetime import datetime
from typing import Optional, List
import structlog

logger = structlog.get_logger()

DEPENDENCY_PATTERNS = [
    r"\bafter\b",
    r"\bonce\b.{0,30}\b(is|are|has|have|get|gets|done|complete|ready)\b",
    r"\bwaiting\s+(on|for)\b",
    r"\bdepends?\s+on\b",
    r"\bblocked\s+(on|by)\b",
    r"\buntil\b.{0,30}\b(is|are|done|complete|finished|ready|approved|merged)\b",
    r"\bcontingent\s+on\b",
    r"\bprerequisite\b",
    r"\bfirst need\b",
    r"\bcan'?t start until\b",
]

_DEPENDENCY_RES = [re.compile(p, re.IGNORECASE) for p in DEPENDENCY_PATTERNS]


def normalize_deadline(raw_deadline: Optional[str]) -> Optional[datetime]:
    """
    Convert a natural language deadline expression to a Python datetime.
    Examples: "next Friday", "end of month", "in two weeks", "EOD Thursday"
    Returns None if parsing fails.
    """
    if not raw_deadline:
        return None
    try:
        import dateparser
        parsed = dateparser.parse(
            raw_deadline,
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
                "DATE_ORDER": "MDY",
                "PREFER_DAY_OF_MONTH": "first",
            }
        )
        return parsed
    except Exception as e:
        logger.debug("Deadline normalization failed", raw=raw_deadline, error=str(e))
        return None


def has_dependency_language(text: str) -> bool:
    """Return True if the text contains dependency/blocking language."""
    return any(r.search(text) for r in _DEPENDENCY_RES)


def extract_assignee_hint(text: str, known_speakers: Optional[List[str]] = None) -> Optional[str]:
    """
    Attempt to extract the task assignee from text using:
      1. Known speaker names
      2. First-person pronouns → CURRENT_SPEAKER
      3. Explicit name patterns ("Alice will...", "Bob needs to...")
    """
    text_lower = text.lower()

    # Known speaker name in text
    if known_speakers:
        for speaker in known_speakers:
            if speaker.lower() in text_lower:
                return speaker

    # First-person
    if re.search(r"\b(i'?ll|i will|i'm going to|i need to|i can|i should)\b", text_lower):
        return "CURRENT_SPEAKER"

    # "Name will..." or "Name needs to..."
    match = re.search(
        r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(will|needs? to|is going to|should)\b",
        text
    )
    if match:
        return match.group(1)

    return None
