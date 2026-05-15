"""
Transcript token stabilizer.

Streaming ASR produces unstable output: early tokens may change as the
model sees more context.  A token becomes "stable" once it appears
unchanged across k consecutive windows.

Algorithm:
  - Maintain a deque of the last k window token lists
  - For each position i, check if all k windows agree on the same token
  - If yes: mark stable and add to permanent output
"""

from typing import List, Tuple, Dict
from collections import deque
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class StableToken:
    word: str
    start: float
    end: float
    occurrences: int = 1
    is_stable: bool = False


class TranscriptStabilizer:
    """
    k-window token stabilization.
    k=3 → token must appear in 3 consecutive windows unchanged.
    """

    def __init__(self, k: int = 3):
        self.k = k
        self.window_history: deque = deque(maxlen=k)
        self.stable_tokens: List[StableToken] = []
        # Track which positional keys we've already committed
        self._committed: Dict[str, bool] = {}

    def process_window(
        self,
        tokens: List[str],
        timestamps: List[Tuple[float, float]],
    ) -> List[StableToken]:
        """
        Submit a new window of tokens.
        Returns newly stabilized tokens since last call.
        tokens and timestamps must be aligned (same length).
        """
        self.window_history.append(tokens)

        if len(self.window_history) < self.k:
            return []   # not enough history

        newly_stable = []
        min_len = min(len(w) for w in self.window_history)

        for i in range(min_len):
            words_at_i = [w[i] for w in self.window_history if i < len(w)]

            if len(words_at_i) == self.k and len(set(words_at_i)) == 1:
                word = words_at_i[0]
                key = f"{i}:{word}"

                if key not in self._committed:
                    start, end = timestamps[i] if i < len(timestamps) else (0.0, 0.0)
                    token = StableToken(
                        word=word,
                        start=start,
                        end=end,
                        occurrences=self.k,
                        is_stable=True,
                    )
                    self._committed[key] = True
                    self.stable_tokens.append(token)
                    newly_stable.append(token)

        return newly_stable

    def get_stable_text(self) -> str:
        """Return the full stable transcript as a single string."""
        return " ".join(t.word.strip() for t in self.stable_tokens)

    def reset(self):
        self.window_history.clear()
        self.stable_tokens.clear()
        self._committed.clear()
