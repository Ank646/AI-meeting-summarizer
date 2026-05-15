"""
Redis Streams Producer — replaces direct Celery dispatch from the WebSocket gateway.

Why Redis Streams instead of direct Celery:
  ─ Backpressure: MAXLEN cap limits stream size; producers slow gracefully
  ─ Durability: messages persist even if all workers are down
  ─ Replay: consumer groups can rewind and re-process on failure
  ─ Fan-out: multiple consumer groups can read the same stream independently
    (e.g. ASR group + analytics group)

Stream name convention:
  aiexec:audio:{meeting_id}    ← raw audio chunks
  aiexec:asr:{meeting_id}      ← whisper transcript segments
  aiexec:diarized:{meeting_id} ← speaker-aligned transcript
"""

import base64
import json
import time
from typing import Optional
import redis.asyncio as aioredis
import structlog
from core.config import settings

logger = structlog.get_logger()

# Maximum messages kept in each stream (oldest are trimmed)
STREAM_MAXLEN = 5_000

# Stream names
AUDIO_STREAM     = "aiexec:audio:{meeting_id}"
ASR_STREAM       = "aiexec:asr:{meeting_id}"
DIARIZED_STREAM  = "aiexec:diarized:{meeting_id}"
EXTRACTED_STREAM = "aiexec:extracted:{meeting_id}"

_pool: Optional[aioredis.Redis] = None


async def _get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=100,
        )
    return _pool


async def publish_audio_chunk(
    meeting_id: str,
    org_id: str,
    audio_b64: str,
    chunk_index: int,
    offset_sec: float,
    is_webm: bool = False,
) -> str:
    """
    Push a raw audio chunk into the audio stream.
    Returns the Redis stream message ID.

    Backpressure: MAXLEN=5000 ensures memory is bounded.
    If consumers fall behind, the oldest unread messages are trimmed,
    signalling producers to throttle (checked via XLEN).
    """
    r = await _get_redis()
    stream = AUDIO_STREAM.format(meeting_id=meeting_id)

    msg_id = await r.xadd(
        stream,
        {
            "meeting_id":  meeting_id,
            "org_id":      org_id,
            "audio":       audio_b64,
            "chunk_index": str(chunk_index),
            "offset_sec":  str(offset_sec),
            "is_webm":     "1" if is_webm else "0",
            "ts":          str(time.time()),
        },
        maxlen=STREAM_MAXLEN,
        approximate=True,  # ~MAXLEN — faster than exact trimming
    )
    logger.debug("Audio chunk published", stream=stream, chunk=chunk_index, msg_id=msg_id)
    return msg_id


async def publish_asr_result(
    meeting_id: str,
    org_id: str,
    segments: list,
    chunk_index: int,
    offset_sec: float,
) -> str:
    """Push Whisper ASR segments into the ASR result stream."""
    r = await _get_redis()
    stream = ASR_STREAM.format(meeting_id=meeting_id)

    msg_id = await r.xadd(
        stream,
        {
            "meeting_id":  meeting_id,
            "org_id":      org_id,
            "segments":    json.dumps(segments),
            "chunk_index": str(chunk_index),
            "offset_sec":  str(offset_sec),
            "ts":          str(time.time()),
        },
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    return msg_id


async def publish_diarized_result(
    meeting_id: str,
    org_id: str,
    utterances: list,
    full_text: str,
    chunk_index: int,
    offset_sec: float,
) -> str:
    """Push diarized (speaker-labelled) transcript into the diarized stream."""
    r = await _get_redis()
    stream = DIARIZED_STREAM.format(meeting_id=meeting_id)

    msg_id = await r.xadd(
        stream,
        {
            "meeting_id":  meeting_id,
            "org_id":      org_id,
            "utterances":  json.dumps(utterances),
            "full_text":   full_text,
            "chunk_index": str(chunk_index),
            "offset_sec":  str(offset_sec),
            "ts":          str(time.time()),
        },
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    return msg_id


async def get_stream_lag(meeting_id: str) -> dict:
    """
    Return stream depths for backpressure monitoring.
    If any stream has lag > threshold, producers should slow down.
    """
    r = await _get_redis()
    results = {}
    for name, tmpl in [
        ("audio", AUDIO_STREAM),
        ("asr",   ASR_STREAM),
        ("diar",  DIARIZED_STREAM),
    ]:
        stream = tmpl.format(meeting_id=meeting_id)
        try:
            length = await r.xlen(stream)
            results[name] = length
        except Exception:
            results[name] = 0
    return results


async def create_consumer_groups(meeting_id: str):
    """
    Create consumer groups for each stream.
    Call this when a meeting starts.
    Groups: asr-workers, diar-workers, extraction-workers
    """
    r = await _get_redis()
    configs = [
        (AUDIO_STREAM.format(meeting_id=meeting_id),    "asr-workers"),
        (ASR_STREAM.format(meeting_id=meeting_id),       "diar-workers"),
        (DIARIZED_STREAM.format(meeting_id=meeting_id),  "extraction-workers"),
    ]
    for stream, group in configs:
        try:
            await r.xgroup_create(stream, group, id="$", mkstream=True)
            logger.info("Consumer group created", stream=stream, group=group)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.warning("Group create failed", stream=stream, error=str(e))


async def cleanup_meeting_streams(meeting_id: str):
    """Delete all streams for a completed meeting (after data is persisted)."""
    r = await _get_redis()
    streams = [
        AUDIO_STREAM.format(meeting_id=meeting_id),
        ASR_STREAM.format(meeting_id=meeting_id),
        DIARIZED_STREAM.format(meeting_id=meeting_id),
        EXTRACTED_STREAM.format(meeting_id=meeting_id),
    ]
    for stream in streams:
        await r.delete(stream)
    logger.info("Meeting streams cleaned up", meeting_id=meeting_id)
