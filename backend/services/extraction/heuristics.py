"""
Layer 1 — Heuristic candidate filter.

Scans transcript sentences with compiled regex patterns to quickly
identify sentences likely to contain tasks, decisions, or risks.

This is a cheap pre-filter that avoids sending every sentence to the LLM.
Only sentences that pass heuristic scoring proceed to LLM classification.
"""

import re
from typing import List
from dataclasses import dataclass, field
from enum import Enum


class CandidateType(str, Enum):
    TASK = "task"
    DECISION = "decision"
    RISK = "risk"
    DEADLINE = "deadline"


@dataclass
class HeuristicCandidate:
    sentence: str
    candidate_types: List[CandidateType] = field(default_factory=list)
    matched_patterns: List[str] = field(default_factory=list)
    vague_score: float = 0.0   # 0.0 (crisp) → 1.0 (very vague)


# ── Pattern Banks ─────────────────────────────────────────────────────────────

TASK_PATTERNS = [
    r"\bwill\s+(do|handle|take care|work on|fix|implement|deliver|send|update|create|build|review|check|follow up|look into)\b",
    r"\b(let'?s|let us)\s+(do|handle|work on|make|create|schedule|set up|discuss|review)\b",
    r"\b(need|needs)\s+to\b",
    r"\b(going to|gonna)\s+\w+",
    r"\b(action item|TODO|to-do|to do|task|next step)\b",
    r"\b(assign|assigned to|responsible for|owner|owns)\b",
    r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bby\s+(eod|eow|end of day|end of week|end of month|end of quarter)\b",
    r"\bby\s+(next|this)\s+\w+",
    r"\b(deadline|due date|due by)\b",
    r"\b(deliver|submit|send|provide|prepare|complete|finish)\b.{5,60}\b(by|before|until|on)\b",
    r"\bI'?ll\s+(take|handle|do|check|send|write|build|fix|update|create|review)\b",
]

DECISION_PATTERNS = [
    r"\b(we('ve| have)? decided|decision is|we('re| are) going with|approved|agreed to|confirmed)\b",
    r"\b(going forward|from now on|moving forward|henceforth)\b",
    r"\bwill\s+(use|adopt|implement|deploy|switch to|migrate to|keep|drop|remove|replace)\b",
    r"\b(chose|chosen|selected|picked|finalized|locked in)\b",
    r"\b(no longer|discontinue|deprecated|shutting down)\b",
    r"\b(stick with|stay with|go with|commit to)\b",
    r"\b(final answer|final decision|settled on)\b",
    r"\b(we('ve| have)? agreed|everyone agrees|consensus is)\b",
]

RISK_PATTERNS = [
    r"\b(blocked|blocking|blocker|bottleneck)\b",
    r"\b(waiting on|waiting for)\b",
    r"\b(depends? on|dependency|dependent on)\b",
    r"\b(risk|risky|concern|issue|problem|challenge|obstacle|impediment)\b",
    r"\b(delay|delayed|behind schedule|off track|slipping|at risk)\b",
    r"\b(can'?t proceed|unable to|won'?t be able|can'?t continue)\b",
    r"\b(missing|lack of|without|no)\b.{0,30}\b(data|access|resource|approval|sign.?off|budget)\b",
    r"\b(capacity|bandwidth|not enough people|understaffed|overloaded)\b",
    r"\b(deadline at risk|might miss|won'?t make it)\b",
]

VAGUE_PATTERNS = [
    r"\bmaybe\b",
    r"\bprobably\b",
    r"\bshould\b",
    r"\bmight\b",
    r"\btry\s+to\b",
    r"\bsometime\b",
    r"\bsoon\b",
    r"\basap\b",
    r"\bat some point\b",
    r"\bwhen possible\b",
    r"\bif\s+(we can|possible|time permits|we get to it)\b",
    r"\b(roughly|approximately|around|about)\b",
    r"\bsomeone\b.{0,30}\b(should|will|needs to)\b",
    r"\bwe should\b",
    r"\bwe could\b",
    r"\bideally\b",
    r"\bhopefully\b",
]


class HeuristicFilter:
    """Compiled regex filter for candidate sentence detection."""

    def __init__(self):
        flags = re.IGNORECASE
        self._task_re = [re.compile(p, flags) for p in TASK_PATTERNS]
        self._decision_re = [re.compile(p, flags) for p in DECISION_PATTERNS]
        self._risk_re = [re.compile(p, flags) for p in RISK_PATTERNS]
        self._vague_re = [re.compile(p, flags) for p in VAGUE_PATTERNS]
        self._vague_total = len(self._vague_re)

    def filter_candidates(self, text: str) -> List[HeuristicCandidate]:
        """
        Split text into sentences and return those that match
        at least one task/decision/risk pattern, or have a high vague score.
        """
        sentences = self._split_sentences(text)
        candidates = []
        for sentence in sentences:
            c = self._score_sentence(sentence)
            if c.candidate_types or c.vague_score >= 0.25:
                candidates.append(c)
        return candidates

    def has_actionable_content(self, text: str) -> bool:
        """Quick check: does this text warrant LLM extraction?"""
        return bool(self.filter_candidates(text))

    def _score_sentence(self, sentence: str) -> HeuristicCandidate:
        types = []
        matched = []

        for r in self._task_re:
            if r.search(sentence):
                if CandidateType.TASK not in types:
                    types.append(CandidateType.TASK)
                matched.append(r.pattern[:50])

        for r in self._decision_re:
            if r.search(sentence):
                if CandidateType.DECISION not in types:
                    types.append(CandidateType.DECISION)
                matched.append(r.pattern[:50])

        for r in self._risk_re:
            if r.search(sentence):
                if CandidateType.RISK not in types:
                    types.append(CandidateType.RISK)
                matched.append(r.pattern[:50])

        vague_hits = sum(1 for r in self._vague_re if r.search(sentence))
        vague_score = min(1.0, vague_hits / max(1, self._vague_total * 0.25))

        return HeuristicCandidate(
            sentence=sentence,
            candidate_types=types,
            matched_patterns=matched,
            vague_score=vague_score,
        )

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Simple sentence splitter on punctuation and newlines."""
        parts = re.split(r"(?<=[.!?])\s+|(?<=\n)", text)
        return [p.strip() for p in parts if len(p.strip()) >= 15]
