"""
Rolling Context Buffer Manager.

Problem:
  Streaming ASR produces transcript chunks one at a time.
  The LLM extraction engine sees only the current chunk — losing context
  about who is speaking, what was decided before, and the ongoing topic.

Solution:
  Maintain the last k=3 transcript windows per meeting in Redis.
  Before extraction, concatenate: T(i-2) + T(i-1) + T(i)
  This gives the LLM a 30-second (3 × 10s) conversational window.

Why this improves extraction:
  ─ Tasks often span multiple sentences: "We'll need to... before Friday"
    may appear across two chunks
  ─ Pronoun resolution: "He will handle it" requires knowing who "he" is
  ─ Decisions are often confirmed 1-2 turns after being proposed
  ─ The LLM can detect topic shifts when it sees the full conversation arc

Storage:
  Redis List per meeting, capped at k elements (LTRIM).
  Also stores speaker context (last k utterances with speaker labels).
"""

import json
from typing import List, Optional
import redis.asyncio as aioredis
import structlog
from core.config import settings

logger = structlog.get_logger()

CONTEXT_K = 3                    # Number of windows to keep
CONTEXT_TTL_SEC = 3600 * 24     # Expire after 24 hours

_CONTEXT_KEY  = "aiexec:ctx:transcript:{meeting_id}"
_SPEAKER_KEY  = "aiexec:ctx:speakers:{meeting_id}"
_TOPICS_KEY   = "aiexec:ctx:topics:{meeting_id}"

_pool: Optional[aioredis.Redis] = None


async def _redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _pool


# ── Transcript context ─────────────────────────────────────────────────────────

async def push_transcript_chunk(meeting_id: str, chunk_text: str):
    """
    Push a new transcript chunk into the rolling buffer.
    Automatically drops oldest chunk when k+1 items exist.
    """
    r = await _redis()
    key = _CONTEXT_KEY.format(meeting_id=meeting_id)

    async with r.pipeline(transaction=True) as pipe:
        pipe.rpush(key, chunk_text)
        pipe.ltrim(key, -CONTEXT_K, -1)   # keep only last k
        pipe.expire(key, CONTEXT_TTL_SEC)
        await pipe.execute()


async def get_context_window(meeting_id: str) -> str:
    """
    Return the last k transcript chunks concatenated.
    This is the input context for the LLM extraction engine.

    Example (k=3, 10s chunks):
      "...chunk i-2 text... [NEXT] ...chunk i-1 text... [NEXT] ...chunk i text..."
    """
    r = await _redis()
    key = _CONTEXT_KEY.format(meeting_id=meeting_id)
    chunks = await r.lrange(key, 0, -1)   # returns list of strings

    if not chunks:
        return ""

    return " [NEXT] ".join(chunks)


async def get_context_as_list(meeting_id: str) -> List[str]:
    """Return context chunks as a list (useful for prompt building)."""
    r = await _redis()
    key = _CONTEXT_KEY.format(meeting_id=meeting_id)
    return await r.lrange(key, 0, -1)


# ── Speaker context ────────────────────────────────────────────────────────────

async def push_speaker_utterance(meeting_id: str, speaker: str, text: str):
    """
    Maintain a rolling list of the last k speaker utterances.
    Used to resolve pronouns and attribute statements to speakers.
    """
    r = await _redis()
    key = _SPEAKER_KEY.format(meeting_id=meeting_id)
    entry = json.dumps({"speaker": speaker, "text": text[:200]})

    async with r.pipeline(transaction=True) as pipe:
        pipe.rpush(key, entry)
        pipe.ltrim(key, -CONTEXT_K * 3, -1)   # keep 9 utterances (3 per chunk avg)
        pipe.expire(key, CONTEXT_TTL_SEC)
        await pipe.execute()


async def get_speaker_context(meeting_id: str) -> str:
    """
    Return a speaker context string for the LLM prompt.
    Format: "Alice: we need to... Bob: I'll handle the..."
    """
    r = await _redis()
    key = _SPEAKER_KEY.format(meeting_id=meeting_id)
    entries = await r.lrange(key, 0, -1)

    lines = []
    for e in entries:
        try:
            obj = json.loads(e)
            lines.append(f"{obj['speaker']}: {obj['text']}")
        except Exception:
            pass
    return "\n".join(lines)


# ── Topic context ──────────────────────────────────────────────────────────────

async def update_detected_topics(meeting_id: str, topics: List[str]):
    """Accumulate topics detected across chunks for topic continuity."""
    r = await _redis()
    key = _TOPICS_KEY.format(meeting_id=meeting_id)
    if topics:
        await r.sadd(key, *topics)
        await r.expire(key, CONTEXT_TTL_SEC)


async def get_detected_topics(meeting_id: str) -> List[str]:
    r = await _redis()
    key = _TOPICS_KEY.format(meeting_id=meeting_id)
    return list(await r.smembers(key))


# ── Full context package for LLM ──────────────────────────────────────────────

async def build_extraction_context(meeting_id: str, current_text: str) -> dict:
    """
    Build the complete context object passed to the LLM extraction engine.
    Includes rolling transcript window + speaker history + topic state.

    Context window:  T(i-2) + T(i-1) + T(i)
    Speaker context: Last 9 utterances with labels
    Topics:          All topics detected so far in this meeting
    """
    await push_transcript_chunk(meeting_id, current_text)

    context_text    = await get_context_window(meeting_id)
    speaker_context = await get_speaker_context(meeting_id)
    topics          = await get_detected_topics(meeting_id)

    return {
        "context_window":   context_text,
        "speaker_context":  speaker_context,
        "known_topics":     topics,
        "current_chunk":    current_text,
    }
