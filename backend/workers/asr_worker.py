"""
Dedicated ASR Celery Worker.

Rationale for separation from diarization:
  ─ Whisper (ASR) is VRAM-heavy: large-v3 uses ~10GB GPU memory
  ─ pyannote (diarization) is smaller but runs better on its own VRAM budget
  ─ Running both in the same process causes memory contention and OOM errors
  ─ Separate workers can be placed on different GPUs or different GPU nodes
  ─ ASR worker can be scaled independently (more meetings → more ASR workers)
  ─ Failure isolation: ASR crash doesn't kill diarization state

GPU Batching:
  - Workers collect multiple audio chunks from the queue
  - Group by sample rate/duration for optimal batch size
  - ctranslate2 batched inference reduces per-chunk GPU kernel overhead
  - Target: 4-8 chunks per batch (tunable via BATCH_SIZE env var)

Queue: 'asr'  (separate from 'audio_pipeline' and 'diarization')
"""

import asyncio
import base64
import structlog
from celery import Celery
from core.config import settings

logger = structlog.get_logger()

celery_app = Celery(
    "aiexec_asr",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # process one at a time for GPU memory safety
    task_routes={
        "workers.asr_worker.run_asr_on_chunk": {"queue": "asr"},
    },
)


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="workers.asr_worker.run_asr_on_chunk",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def run_asr_on_chunk(
    self,
    meeting_id: str,
    org_id: str,
    audio_b64: str,
    chunk_index: int,
    offset_sec: float,
    is_webm: bool = False,
):
    """
    GPU-bound ASR task:
      1. Decode and preprocess audio
      2. VAD filter
      3. Whisper transcription → word timestamps
      4. Publish ASR result to Redis Stream (for diarization worker)

    Separated from diarization so:
      - GPU memory for Whisper is released before pyannote loads
      - Workers can be placed on different GPUs
      - ASR pool can be scaled independently
    """
    audio_bytes = base64.b64decode(audio_b64)
    try:
        return run_async(
            _asr_async(meeting_id, org_id, audio_bytes, chunk_index, offset_sec, is_webm)
        )
    except Exception as exc:
        logger.error("ASR task failed", error=str(exc), chunk=chunk_index)
        raise self.retry(exc=exc)


async def _asr_async(
    meeting_id: str,
    org_id: str,
    audio_bytes: bytes,
    chunk_index: int,
    offset_sec: float,
    is_webm: bool,
):
    from services.audio.preprocessor import AudioPreprocessor
    from services.audio.vad import VoiceActivityDetector
    from services.asr.whisper_service import whisper_service
    from services.queue.stream_producer import publish_asr_result

    preprocessor = AudioPreprocessor()
    vad = VoiceActivityDetector(aggressiveness=2)

    # Step 1 — preprocess
    audio = (
        await preprocessor.preprocess_bytes(audio_bytes, "webm")
        if is_webm
        else await preprocessor.preprocess_pcm(audio_bytes)
    )

    # Step 2 — VAD
    speech_audio, speech_segs = vad.filter_speech(audio)
    if not speech_segs:
        logger.debug("ASR worker: silence only", chunk=chunk_index)
        return {"status": "silence"}

    # Step 3 — Whisper ASR
    asr_segments = await whisper_service.transcribe_chunk(speech_audio)
    if not asr_segments:
        return {"status": "no_speech"}

    # Serialize for Redis Stream
    segments_data = []
    for seg in asr_segments:
        segments_data.append({
            "text": seg.text,
            "start": seg.start + offset_sec,
            "end":   seg.end   + offset_sec,
            "words": [
                {
                    "word":  w.word,
                    "start": w.start + offset_sec,
                    "end":   w.end   + offset_sec,
                    "prob":  w.probability,
                }
                for w in seg.words
            ],
        })

    # Step 4 — push to ASR stream → diarization worker picks up
    await publish_asr_result(
        meeting_id, org_id, segments_data, chunk_index, offset_sec
    )

    logger.info("ASR complete", meeting_id=meeting_id, chunk=chunk_index,
                segments=len(segments_data))
    return {"status": "ok", "segments": len(segments_data)}
