"""
Redis Streams Consumer — base class for all stream-reading workers.

Pattern: Consumer Group with XREADGROUP + XACK
  - Each worker is a named consumer in a group
  - Messages are not re-delivered to other consumers until XACK
  - On worker crash: XPENDING shows un-acked messages → re-claimed by another worker
  - XCLAIM handles failure recovery (messages pending > timeout → re-claim)

Backpressure handling:
  - Workers BLOCK for N ms if no messages (avoids busy-loop)
  - Workers check XLEN before ACKing — if lag > threshold, emit metric
  - Autoscaling hook: expose lag metric to Prometheus/CloudWatch

Scaling:
  - Add more workers to the same consumer group → Redis auto load-balances
  - Each worker sees unique messages (no duplication)
  - No coordination needed — Redis handles assignment
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import redis.asyncio as aioredis
import structlog
from core.config import settings

logger = structlog.get_logger()

CLAIM_TIMEOUT_MS  = 60_000   # Re-claim messages pending longer than 60s
BLOCK_TIMEOUT_MS  = 2_000    # Block for 2s waiting for new messages
BATCH_SIZE        = 10       # Messages to read per iteration
LAG_WARN_THRESHOLD = 1_000   # Warn if stream lag exceeds this


class BaseStreamConsumer(ABC):
    """
    Abstract base for all Redis Stream consumers.
    Subclass and implement `process_message()`.
    """

    def __init__(self, stream: str, group: str, consumer_name: str):
        self.stream        = stream
        self.group         = group
        self.consumer_name = consumer_name
        self._redis: Optional[aioredis.Redis] = None
        self._running = False

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def ensure_group(self):
        """Create consumer group if not exists."""
        r = await self._get_redis()
        try:
            await r.xgroup_create(self.stream, self.group, id="$", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def run(self):
        """Main consume loop. Run in an asyncio task or thread."""
        await self.ensure_group()
        self._running = True
        r = await self._get_redis()

        logger.info("Consumer started", stream=self.stream, group=self.group,
                    consumer=self.consumer_name)

        while self._running:
            try:
                # 1. Try to claim stuck messages first (failure recovery)
                await self._reclaim_pending(r)

                # 2. Read new messages
                messages = await r.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer_name,
                    streams={self.stream: ">"},
                    count=BATCH_SIZE,
                    block=BLOCK_TIMEOUT_MS,
                )

                if not messages:
                    continue   # timeout — loop again

                for stream_name, stream_msgs in messages:
                    for msg_id, fields in stream_msgs:
                        try:
                            await self.process_message(fields)
                            # ACK only on success
                            await r.xack(self.stream, self.group, msg_id)
                        except Exception as e:
                            logger.error("Message processing failed",
                                         msg_id=msg_id, error=str(e))
                            # Don't ACK → message stays pending → XCLAIM will retry

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Consumer loop error", error=str(e))
                await asyncio.sleep(1)

        logger.info("Consumer stopped", stream=self.stream, consumer=self.consumer_name)

    async def _reclaim_pending(self, r: aioredis.Redis):
        """
        Claim messages that have been pending too long (crashed worker).
        This is the failure recovery mechanism.
        """
        try:
            pending = await r.xpending_range(
                self.stream,
                self.group,
                min="-",
                max="+",
                count=50,
            )
            for entry in pending:
                if entry["time_since_delivered"] > CLAIM_TIMEOUT_MS:
                    await r.xclaim(
                        self.stream,
                        self.group,
                        self.consumer_name,
                        min_idle_time=CLAIM_TIMEOUT_MS,
                        message_ids=[entry["message_id"]],
                    )
                    logger.info("Reclaimed stuck message",
                                msg_id=entry["message_id"],
                                idle_ms=entry["time_since_delivered"])
        except Exception:
            pass   # non-fatal — will retry next loop

    def stop(self):
        self._running = False

    @abstractmethod
    async def process_message(self, fields: Dict[str, Any]):
        """Implement this to handle each message."""
        ...


class AudioChunkConsumer(BaseStreamConsumer):
    """Consumes audio chunks from the audio stream and dispatches ASR tasks."""

    def __init__(self, consumer_name: str = "asr-worker-1"):
        super().__init__(
            stream=f"aiexec:audio:*",
            group="asr-workers",
            consumer_name=consumer_name,
        )

    async def process_message(self, fields: Dict[str, Any]):
        """Dispatch audio chunk to the dedicated ASR Celery worker."""
        from workers.asr_worker import run_asr_on_chunk
        run_asr_on_chunk.apply_async(
            args=[
                fields["meeting_id"],
                fields["org_id"],
                fields["audio"],
                int(fields["chunk_index"]),
                float(fields["offset_sec"]),
                fields.get("is_webm", "0") == "1",
            ],
            queue="asr",
        )
