"""
Speaker diarization using pyannote.audio 3.1.

Produces speaker segments: (start_sec, end_sec, speaker_label)
Then aligns each Whisper word to its speaker using timestamp intersection.

Requires:
  - HF_TOKEN env var (HuggingFace access token)
  - Accepted model agreement at: https://hf.co/pyannote/speaker-diarization-3.1

Falls back to single-speaker mode if pipeline cannot be loaded.
"""

import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
import structlog
from core.config import settings

logger = structlog.get_logger()


@dataclass
class SpeakerSegment:
    start: float
    end: float
    speaker: str


@dataclass
class DiarizedWord:
    word: str
    start: float
    end: float
    speaker: str
    probability: float


class SpeakerDiarizer:
    """Lazy-loaded pyannote.audio diarization pipeline."""

    def __init__(self):
        self._pipeline = None
        self._load_attempted = False

    def _load_pipeline(self):
        if self._load_attempted:
            return
        self._load_attempted = True

        if not settings.hf_token:
            logger.warning("HF_TOKEN not set — diarization disabled, using single-speaker fallback")
            return

        try:
            from pyannote.audio import Pipeline
            import torch

            logger.info("Loading pyannote diarization pipeline...")
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=settings.hf_token,
            )
            device = "cuda" if settings.whisper_device == "cuda" else "cpu"
            self._pipeline = self._pipeline.to(torch.device(device))
            logger.info("Diarization pipeline loaded", device=device)
        except Exception as e:
            logger.error("Failed to load diarization pipeline", error=str(e))
            self._pipeline = None

    async def diarize(
        self,
        audio: "np.ndarray",
        sample_rate: int = 16000,
        num_speakers: Optional[int] = None,
    ) -> List[SpeakerSegment]:
        """
        Run speaker diarization on a float32 audio array.
        Returns list of (start, end, speaker) segments.
        Falls back to single-speaker if pipeline unavailable.
        """
        self._load_pipeline()

        if self._pipeline is None:
            duration = len(audio) / sample_rate
            return [SpeakerSegment(start=0.0, end=duration, speaker="SPEAKER_00")]

        import torch
        import numpy as np

        audio_tensor = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
        loop = asyncio.get_event_loop()

        try:
            diarization = await loop.run_in_executor(
                None,
                lambda: self._pipeline(
                    {"waveform": audio_tensor, "sample_rate": sample_rate},
                    **({"num_speakers": num_speakers} if num_speakers else {}),
                )
            )

            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(SpeakerSegment(
                    start=turn.start,
                    end=turn.end,
                    speaker=speaker,
                ))
            logger.debug("Diarization complete", num_segments=len(segments))
            return segments

        except Exception as e:
            logger.error("Diarization inference failed", error=str(e))
            duration = len(audio) / sample_rate
            return [SpeakerSegment(start=0.0, end=duration, speaker="SPEAKER_00")]

    def align_words_to_speakers(
        self,
        words: List[Dict],
        segments: List[SpeakerSegment],
    ) -> List[DiarizedWord]:
        """
        Assign a speaker label to each word.
        speaker(word) = speaker_j  if  s_j ≤ t_word_midpoint ≤ e_j

        words: [{"word": str, "start": float, "end": float, "probability": float}]
        """
        result = []
        for w in words:
            mid = (w["start"] + w["end"]) / 2.0
            speaker = self._find_speaker(mid, segments)
            result.append(DiarizedWord(
                word=w["word"],
                start=w["start"],
                end=w["end"],
                speaker=speaker,
                probability=w.get("probability", 1.0),
            ))
        return result

    def _find_speaker(self, timestamp: float, segments: List[SpeakerSegment]) -> str:
        """Return speaker whose segment contains the given timestamp. UNKNOWN if none."""
        for seg in segments:
            if seg.start <= timestamp <= seg.end:
                return seg.speaker
        # Nearest segment fallback
        if segments:
            nearest = min(segments, key=lambda s: abs((s.start + s.end) / 2 - timestamp))
            return nearest.speaker
        return "UNKNOWN"

    def group_by_speaker(self, diarized_words: List[DiarizedWord]) -> List[Dict]:
        """
        Merge consecutive words by the same speaker into utterances.
        Returns: [{"speaker": str, "text": str, "start": float, "end": float}]
        """
        if not diarized_words:
            return []

        utterances = []
        current_speaker = diarized_words[0].speaker
        current_words = [diarized_words[0]]

        for w in diarized_words[1:]:
            if w.speaker == current_speaker:
                current_words.append(w)
            else:
                utterances.append({
                    "speaker": current_speaker,
                    "text": " ".join(cw.word.strip() for cw in current_words),
                    "start": current_words[0].start,
                    "end": current_words[-1].end,
                })
                current_speaker = w.speaker
                current_words = [w]

        if current_words:
            utterances.append({
                "speaker": current_speaker,
                "text": " ".join(cw.word.strip() for cw in current_words),
                "start": current_words[0].start,
                "end": current_words[-1].end,
            })

        return utterances


# Module-level singleton
diarizer = SpeakerDiarizer()
