import json
import redis.asyncio as aioredis
from core.config import settings

_redis_pool: aioredis.Redis = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def publish_event(channel: str, event: dict):
    """Publish a JSON event to a Redis pub/sub channel."""
    r = await get_redis()
    await r.publish(channel, json.dumps(event, default=str))


async def subscribe_to_channel(channel: str):
    """
    Async generator that yields decoded JSON messages from a Redis pub/sub channel.
    Creates its own connection to avoid sharing with the pool.
    """
    r = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except json.JSONDecodeError:
                    yield {"raw": message["data"]}
    finally:
        await pubsub.unsubscribe(channel)
        await r.aclose()


async def set_with_ttl(key: str, value: dict, ttl_sec: int = 3600):
    r = await get_redis()
    await r.setex(key, ttl_sec, json.dumps(value, default=str))


async def get_cached(key: str) -> dict | None:
    r = await get_redis()
    val = await r.get(key)
    if val:
        return json.loads(val)
    return None
