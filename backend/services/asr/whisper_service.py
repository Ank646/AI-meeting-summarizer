"""
Streaming ASR using faster-whisper (CTranslate2 backend).

Pipeline:
  audio chunk (np.ndarray, 16kHz float32)
    → WhisperModel.transcribe()
    → word-level timestamps
    → TranscriptSegment list

Sliding window:
  Window W = 10s, Stride S = 8s, Overlap O = 2s
  C_i = A[i*S : i*S + W]
  Context H_i = transcripts of last 3 chunks (injected as initial_prompt)
"""

import asyncio
from typing import List, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass, field
import structlog
from core.config import settings

logger = structlog.get_logger()

SAMPLE_RATE = 16000

# Business domain vocabulary injected as prompt bias
DOMAIN_VOCABULARY = [
    "sprint", "backlog", "API", "deployment", "microservice", "stakeholder",
    "deliverable", "KPI", "SLA", "MVP", "blocker", "retrospective", "kanban",
    "roadmap", "milestone", "OKR", "scrum", "Jira", "pull request", "refactor",
]


@dataclass
class WordToken:
    word: str
    start: float       # seconds
    end: float
    probability: float


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: List[WordToken] = field(default_factory=list)
    language: str = "en"
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


class WhisperService:
    """Thread-safe singleton ASR service."""

    def __init__(self):
        self._model = None
        self._lock = asyncio.Lock()

    def _load_model(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        logger.info(
            "Loading Whisper model",
            size=settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        self._model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            cpu_threads=4,
            num_workers=2,
            download_root="/root/.cache/whisper",
        )
        logger.info("Whisper model loaded")

    async def transcribe_chunk(
        self,
        audio: "np.ndarray",
        initial_prompt: Optional[str] = None,
        language: str = "en",
    ) -> List[TranscriptSegment]:
        """
        Transcribe one audio chunk synchronously in a thread pool executor.
        Returns segments with word-level timestamps.
        """
        self._load_model()
        prompt = self._build_prompt(initial_prompt)

        loop = asyncio.get_event_loop()
        result_segments, info = await loop.run_in_executor(
            None,
            lambda: self._model.transcribe(
                audio,
                language=language,
                initial_prompt=prompt,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "threshold": 0.5,
                    "speech_pad_ms": 200,
                },
                beam_size=5,
                best_of=5,
                temperature=[0.0, 0.2, 0.4],
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )
        )

        segments = []
        for seg in result_segments:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(WordToken(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=w.probability,
                    ))
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                words=words,
                language=info.language,
                avg_logprob=seg.avg_logprob,
                no_speech_prob=seg.no_speech_prob,
            ))

        return [s for s in segments if s.text and s.no_speech_prob < 0.6]

    async def transcribe_streaming(
        self,
        audio_queue: asyncio.Queue,
    ) -> AsyncGenerator[Tuple[List[TranscriptSegment], int], None]:
        """
        Consume audio chunks from an asyncio.Queue and yield
        (segments, chunk_index) as they become available.

        Maintains a rolling context of the last 3 chunk transcripts
        to inject as initial_prompt for improved continuity.
        """
        chunk_index = 0
        context_history: List[str] = []

        while True:
            audio_chunk = await audio_queue.get()
            if audio_chunk is None:
                break   # sentinel: end of stream

            prompt = " ".join(context_history[-3:]) if context_history else None
            segments = await self.transcribe_chunk(audio_chunk, initial_prompt=prompt)

            if segments:
                context_history.append(" ".join(s.text for s in segments))
                if len(context_history) > 5:
                    context_history.pop(0)

            yield segments, chunk_index
            chunk_index += 1
            audio_queue.task_done()

    def _build_prompt(self, base_prompt: Optional[str]) -> str:
        domain_hint = ", ".join(DOMAIN_VOCABULARY[:10])
        system_hint = f"Business meeting transcript. Domain terms: {domain_hint}."
        if base_prompt:
            return f"{base_prompt} {system_hint}"
        return system_hint


# Module-level singleton
whisper_service = WhisperService()
