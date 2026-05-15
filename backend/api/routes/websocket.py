"""
WebSocket gateway — two endpoints:

  /ws/audio/{meeting_id}     — receives raw PCM frames from browser mic
  /ws/dashboard/{meeting_id} — pushes live intelligence events to browser UI

Audio flow:
  Browser → PCM int16 binary frames (20ms, 16kHz mono)
         → server accumulates in a sliding window buffer
         → dispatches 10s chunks to Celery worker every 8s
         → worker processes and publishes results to Redis
         → /ws/dashboard subscribers receive events in real time
"""

import asyncio
import base64
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.redis_client import subscribe_to_channel
from core.auth import decode_token
import structlog

router = APIRouter()
logger = structlog.get_logger()

# 10 seconds of 16kHz mono int16 audio
_SAMPLE_RATE = 16000
_BYTES_PER_SAMPLE = 2
_WINDOW_SEC = 10
_STRIDE_SEC = 8
_CHUNK_BYTES = _SAMPLE_RATE * _BYTES_PER_SAMPLE * _WINDOW_SEC   # 320 000 bytes
_STRIDE_BYTES = _SAMPLE_RATE * _BYTES_PER_SAMPLE * _STRIDE_SEC  # 256 000 bytes


@router.websocket("/ws/audio/{meeting_id}")
async def audio_stream(
    websocket: WebSocket,
    meeting_id: str,
    token: str = Query(...),
):
    """
    Receives raw PCM binary frames from the browser microphone.
    Accumulates into 10s windows and dispatches to Celery.
    """
    try:
        payload = decode_token(token)
        org_id = payload.get("org_id")
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("Audio stream connected", meeting_id=meeting_id)

    buffer = bytearray()
    chunk_index = 0

    try:
        async for data in websocket.iter_bytes():
            buffer.extend(data)

            # Once we have a full window, dispatch and slide
            while len(buffer) >= _CHUNK_BYTES:
                chunk_bytes = bytes(buffer[:_CHUNK_BYTES])
                offset_sec = chunk_index * float(_STRIDE_SEC)
                encoded = base64.b64encode(chunk_bytes).decode()

                # Import here to avoid circular imports at module load time
                from workers.pipeline_worker import process_audio_chunk
                process_audio_chunk.apply_async(
                    args=[meeting_id, org_id, encoded, chunk_index, offset_sec, False],
                    queue="audio_pipeline",
                )

                chunk_index += 1
                # Slide window forward by stride
                buffer = buffer[_STRIDE_BYTES:]

    except WebSocketDisconnect:
        logger.info("Audio stream disconnected", meeting_id=meeting_id, total_chunks=chunk_index)

        # Flush any remaining buffered audio
        if len(buffer) >= _SAMPLE_RATE * _BYTES_PER_SAMPLE:  # at least 1 second
            encoded = base64.b64encode(bytes(buffer)).decode()
            from workers.pipeline_worker import process_audio_chunk
            process_audio_chunk.apply_async(
                args=[meeting_id, org_id, encoded, chunk_index, chunk_index * float(_STRIDE_SEC), False],
                queue="audio_pipeline",
            )

    except Exception as e:
        logger.error("Audio stream error", error=str(e), meeting_id=meeting_id)


@router.websocket("/ws/dashboard/{meeting_id}")
async def dashboard_stream(
    websocket: WebSocket,
    meeting_id: str,
    token: str = Query(...),
):
    """
    Pushes real-time intelligence events to the browser dashboard.
    Bridges Redis pub/sub → WebSocket.

    Events: transcript | extraction | score
    """
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    channel = f"meeting:{meeting_id}:events"
    logger.info("Dashboard subscriber connected", meeting_id=meeting_id, channel=channel)

    # Send a connection confirmation immediately
    await websocket.send_text(json.dumps({
        "event_type": "connected",
        "meeting_id": meeting_id,
        "data": {"message": "Streaming intelligence events..."},
    }))

    try:
        async for event in subscribe_to_channel(channel):
            await websocket.send_text(json.dumps(event, default=str))
    except WebSocketDisconnect:
        logger.info("Dashboard subscriber disconnected", meeting_id=meeting_id)
    except Exception as e:
        logger.error("Dashboard stream error", error=str(e))
