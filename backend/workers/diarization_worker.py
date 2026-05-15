"""
Dedicated Diarization Celery Worker.

Consumes from the ASR result stream. Takes Whisper word timestamps and
runs pyannote speaker diarization on the same audio chunk.

Why separate from ASR:
  ─ pyannote model (~3GB) and Whisper large-v3 (~10GB) cannot share one GPU
    without memory swapping overhead
  ─ Diarization is CPU/GPU agnostic — can run on CPU nodes to save GPU budget
  ─ Diarization latency is ~2-4x Whisper latency → separate pool prevents
    head-of-line blocking in the ASR queue
  ─ If diarization fails, ASR results are still available (graceful degradation)

GPU Scaling:
  - Run diarization workers on CPU if GPU is reserved for ASR+LLM
  - Use WHISPER_DEVICE=cuda, diarization can use CPU without quality loss
    (pyannote on CPU is ~3x slower but acceptable for 10s chunks)
  - Target: 1 diarization worker per 2 ASR workers

Queue: 'diarization'
"""

import asyncio
import json
import base64
import structlog
from celery import Celery
from core.config import settings

logger = structlog.get_logger()

celery_app = Celery(
    "aiexec_diarization",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.diarization_worker.run_diarization": {"queue": "diarization"},
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
    name="workers.diarization_worker.run_diarization",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def run_diarization(
    self,
    meeting_id: str,
    org_id: str,
    audio_b64: str,
    asr_segments_json: str,
    chunk_index: int,
    offset_sec: float,
):
    """
    Diarization + alignment task:
      1. Decode audio
      2. Run pyannote speaker diarization
      3. Align Whisper word timestamps to speaker segments
      4. Group into utterances
      5. Push to context buffer
      6. Publish live transcript event to Redis pub/sub
      7. Dispatch extraction task
    """
    audio_bytes = base64.b64decode(audio_b64)
    asr_segments = json.loads(asr_segments_json)
    try:
        return run_async(
            _diarize_async(
                meeting_id, org_id, audio_bytes, asr_segments, chunk_index, offset_sec
            )
        )
    except Exception as exc:
        logger.error("Diarization task failed", error=str(exc))
        raise self.retry(exc=exc)


async def _diarize_async(
    meeting_id: str,
    org_id: str,
    audio_bytes: bytes,
    asr_segments: list,
    chunk_index: int,
    offset_sec: float,
):
    from services.audio.preprocessor import AudioPreprocessor
    from services.diarization.diarizer import diarizer
    from services.context.context_buffer import (
        build_extraction_context, push_speaker_utterance
    )
    from services.queue.stream_producer import publish_diarized_result
    from core.redis_client import publish_event
    from workers.pipeline_worker import run_extraction

    preprocessor = AudioPreprocessor()
    audio = await preprocessor.preprocess_pcm(audio_bytes)

    # Step 1 — speaker diarization on this chunk
    speaker_segs = await diarizer.diarize(audio)

    # Step 2 — extract and align word timestamps
    all_words = []
    for seg in asr_segments:
        for w in seg.get("words", []):
            all_words.append({
                "word":        w["word"],
                "start":       w["start"],
                "end":         w["end"],
                "probability": w["prob"],
            })

    diarized_words = diarizer.align_words_to_speakers(all_words, speaker_segs)
    utterances     = diarizer.group_by_speaker(diarized_words)

    # Step 3 — push to context buffer + speaker context
    full_text = " ".join(seg["text"] for seg in asr_segments)
    for u in utterances:
        await push_speaker_utterance(meeting_id, u["speaker"], u["text"])

    # Step 4 — publish live transcript to dashboard
    is_stable = chunk_index >= settings.stabilization_k
    await publish_event(
        f"meeting:{meeting_id}:events",
        {
            "event_type": "transcript",
            "meeting_id": meeting_id,
            "data": {
                "chunk_index": chunk_index,
                "utterances":  utterances,
                "full_text":   full_text,
                "is_stable":   is_stable,
                "offset_sec":  offset_sec,
            },
        }
    )

    # Step 5 — push to diarized stream (for extraction worker)
    await publish_diarized_result(
        meeting_id, org_id, utterances, full_text, chunk_index, offset_sec
    )

    # Step 6 — dispatch extraction
    run_extraction.apply_async(
        args=[meeting_id, org_id, full_text, utterances, chunk_index, offset_sec],
        queue="extraction",
    )

    logger.info("Diarization complete", meeting_id=meeting_id, chunk=chunk_index,
                utterances=len(utterances))
    return {"status": "ok", "utterances": len(utterances)}
