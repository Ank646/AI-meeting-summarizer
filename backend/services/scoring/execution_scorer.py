"""
Execution Score Engine.

Computes a real-time execution quality score for each meeting.

Formula:
  Exec = 0.4*(O/T) + 0.3*(D/T) - 0.2*(V/T) - 0.1*(B/T)

Where:
  T = total tasks
  O = tasks with a named owner
  D = tasks with a specific deadline
  V = vague commitments (is_vague=True)
  B = active blockers

Score is clamped to [0.0, 1.0].
A score of 1.0 means every task has an owner and deadline with no blockers or vague commitments.
"""

from typing import List
import structlog

logger = structlog.get_logger()


class ExecutionScorer:

    WEIGHTS = {
        "owner":    0.40,
        "deadline": 0.30,
        "vague":   -0.20,
        "blocker": -0.10,
    }

    LABELS = [
        (0.80, "Excellent"),
        (0.60, "Good"),
        (0.40, "Fair"),
        (0.20, "Poor"),
        (0.00, "Critical"),
    ]

    def compute(
        self,
        tasks: list,       # list of ExtractedTask or Task ORM objects
        risks: list,       # list of ExtractedRisk or Risk ORM objects
        meeting_id: str,
        org_id: str,
    ) -> dict:
        """
        Compute execution score from task and risk lists.
        Works with both Pydantic schemas and SQLAlchemy ORM objects.
        """
        T = len(tasks)
        if T == 0:
            return self._empty_score(meeting_id, org_id)

        O = sum(1 for t in tasks if self._get_attr(t, "assignee") or self._get_attr(t, "assignee_name"))
        D = sum(1 for t in tasks if self._get_attr(t, "deadline_raw") or self._get_attr(t, "deadline_iso"))
        V = sum(1 for t in tasks if self._get_attr(t, "is_vague"))
        B = sum(1 for r in risks if self._get_attr(r, "is_blocker"))

        raw = (
            self.WEIGHTS["owner"]   * (O / T) +
            self.WEIGHTS["deadline"] * (D / T) +
            self.WEIGHTS["vague"]   * (V / T) +
            self.WEIGHTS["blocker"] * (B / T)
        )
        score = max(0.0, min(1.0, raw))

        return {
            "score": round(score, 4),
            "tasks_total": T,
            "tasks_with_owner": O,
            "tasks_with_deadline": D,
            "vague_count": V,
            "blocker_count": B,
            "meeting_id": meeting_id,
            "org_id": org_id,
        }

    def get_label(self, score: float) -> str:
        for threshold, label in self.LABELS:
            if score >= threshold:
                return label
        return "Critical"

    def _empty_score(self, meeting_id: str, org_id: str) -> dict:
        return {
            "score": 0.0,
            "tasks_total": 0,
            "tasks_with_owner": 0,
            "tasks_with_deadline": 0,
            "vague_count": 0,
            "blocker_count": 0,
            "meeting_id": meeting_id,
            "org_id": org_id,
        }

    @staticmethod
    def _get_attr(obj, attr: str):
        """Works with both dicts, Pydantic models, and SQLAlchemy ORM objects."""
        if isinstance(obj, dict):
            return obj.get(attr)
        return getattr(obj, attr, None)


# Module-level singleton
execution_scorer = ExecutionScorer()
