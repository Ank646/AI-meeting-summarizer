"""
Celery Pipeline Worker — orchestrates the full per-chunk processing pipeline.

Queues:
  audio_pipeline  — heavy: preprocess → ASR → diarize (GPU)
  extraction      — medium: LLM extraction + DB writes (GPU/CPU)
  graph_update    — light: Neo4j graph writes (CPU)

Each queue can be scaled independently.
"""

import asyncio
import base64
import json
import uuid
from typing import List
import structlog

from celery import Celery
from core.config import settings

logger = structlog.get_logger()

celery_app = Celery(
    "aiexec_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.pipeline_worker.process_audio_chunk": {"queue": "audio_pipeline"},
        "workers.pipeline_worker.run_extraction":      {"queue": "extraction"},
        "workers.pipeline_worker.update_graph":        {"queue": "graph_update"},
    },
)


def run_async(coro):
    """Run an async coroutine synchronously inside a Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Task 1: Audio Processing (GPU-bound) ──────────────────────────────────────

@celery_app.task(
    name="workers.pipeline_worker.process_audio_chunk",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def process_audio_chunk(
    self,
    meeting_id: str,
    org_id: str,
    audio_bytes_b64: str,    # base64-encoded PCM or WebM bytes
    chunk_index: int,
    offset_sec: float,
    is_webm: bool = False,
):
    """
    Main audio pipeline task.
    1. Decode audio bytes
    2. Preprocess (normalize, denoise)
    3. VAD filter
    4. Whisper ASR → word timestamps
    5. Pyannote diarization → speaker segments
    6. Align words to speakers → utterances
    7. Publish live transcript event to Redis
    8. Dispatch extraction task
    """
    audio_bytes = base64.b64decode(audio_bytes_b64)
    try:
        return run_async(
            _process_chunk_async(
                meeting_id, org_id, audio_bytes, chunk_index, offset_sec, is_webm
            )
        )
    except Exception as exc:
        logger.error("process_audio_chunk failed", error=str(exc), chunk=chunk_index)
        raise self.retry(exc=exc)


async def _process_chunk_async(
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
    from services.diarization.diarizer import diarizer
    from core.redis_client import publish_event

    preprocessor = AudioPreprocessor()
    vad = VoiceActivityDetector(aggressiveness=2)

    # Step 1 — preprocess
    if is_webm:
        audio = await preprocessor.preprocess_bytes(audio_bytes, source_format="webm")
    else:
        audio = await preprocessor.preprocess_pcm(audio_bytes)

    # Step 2 — VAD filter
    speech_audio, speech_segments = vad.filter_speech(audio)
    if not speech_segments:
        logger.debug("VAD: silence only", chunk=chunk_index)
        return {"status": "silence", "chunk_index": chunk_index}

    # Step 3 — Whisper ASR
    asr_segments = await whisper_service.transcribe_chunk(speech_audio)
    if not asr_segments:
        return {"status": "no_transcript", "chunk_index": chunk_index}

    # Step 4 — Diarization
    speaker_segs = await diarizer.diarize(speech_audio)

    # Step 5 — Build word list with offset-adjusted timestamps
    all_words = []
    for seg in asr_segments:
        for w in seg.words:
            all_words.append({
                "word": w.word,
                "start": w.start + offset_sec,
                "end":   w.end   + offset_sec,
                "probability": w.probability,
            })

    # Step 6 — Align and group
    diarized_words = diarizer.align_words_to_speakers(all_words, speaker_segs)
    utterances = diarizer.group_by_speaker(diarized_words)
    full_text = " ".join(seg.text for seg in asr_segments)

    # Step 7 — Publish live transcript event
    await publish_event(
        f"meeting:{meeting_id}:events",
        {
            "event_type": "transcript",
            "meeting_id": meeting_id,
            "data": {
                "chunk_index": chunk_index,
                "utterances": utterances,
                "full_text": full_text,
                "is_stable": chunk_index >= settings.stabilization_k,
                "offset_sec": offset_sec,
            },
        }
    )

    # Step 8 — Dispatch extraction
    run_extraction.apply_async(
        args=[meeting_id, org_id, full_text, utterances, chunk_index, offset_sec],
        queue="extraction",
    )

    return {
        "status": "ok",
        "chunk_index": chunk_index,
        "utterances": len(utterances),
        "words": len(all_words),
    }


# ── Task 2: LLM Extraction + DB write ────────────────────────────────────────

@celery_app.task(
    name="workers.pipeline_worker.run_extraction",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def run_extraction(
    self,
    meeting_id: str,
    org_id: str,
    transcript: str,
    utterances: list,
    chunk_index: int,
    offset_sec: float,
):
    try:
        return run_async(
            _run_extraction_async(
                meeting_id, org_id, transcript, utterances, chunk_index, offset_sec
            )
        )
    except Exception as exc:
        logger.error("run_extraction failed", error=str(exc))
        raise self.retry(exc=exc)


async def _run_extraction_async(
    meeting_id: str,
    org_id: str,
    transcript: str,
    utterances: list,
    chunk_index: int,
    offset_sec: float,
):
    from services.extraction.llm_extractor import llm_extractor
    from services.extraction.scorer import normalize_deadline
    from services.scoring.execution_scorer import execution_scorer
    from services.embeddings.embedding_service import embedding_service
    from core.database import AsyncSessionLocal
    from core.redis_client import publish_event
    from models.db_models import Transcript, Task, Decision, Risk, ExecutionScore
    from models.schemas import ExtractedTask as ETSchema
    from sqlalchemy import select

    # Build speaker context for LLM prompt
    speaker_ctx = "; ".join(
        f"{u['speaker']}: {u['text'][:80]}" for u in utterances[:4]
    )

    # LLM extraction (4-layer pipeline)
    result = await llm_extractor.extract(transcript, speaker_context=speaker_ctx)

    async with AsyncSessionLocal() as db:
        # Embed transcript chunk
        embedding = await embedding_service.embed_single(transcript)

        # Store transcript
        t_obj = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting_id,
            org_id=org_id,
            text=transcript,
            start_time=offset_sec,
            end_time=offset_sec + settings.chunk_window_sec,
            is_stable=(chunk_index >= settings.stabilization_k),
            chunk_index=chunk_index,
            embedding=embedding,
        )
        db.add(t_obj)

        # Store tasks
        task_objects = []
        for et in result.tasks:
            deadline_iso = normalize_deadline(et.deadline_raw)
            task_obj = Task(
                id=uuid.uuid4(),
                meeting_id=meeting_id,
                org_id=org_id,
                description=et.description,
                assignee_name=et.assignee,
                deadline_raw=et.deadline_raw,
                deadline_iso=deadline_iso,
                confidence=et.confidence,
                is_vague=et.is_vague,
                source_transcript_id=t_obj.id,
            )
            db.add(task_obj)
            task_objects.append(task_obj)

        # Store decisions
        for ed in result.decisions:
            db.add(Decision(
                id=uuid.uuid4(),
                meeting_id=meeting_id,
                org_id=org_id,
                description=ed.description,
                made_by=ed.made_by,
                rationale=ed.rationale,
                confidence=ed.confidence,
            ))

        # Store risks
        risk_objects = []
        for er in result.risks:
            risk_obj = Risk(
                id=uuid.uuid4(),
                meeting_id=meeting_id,
                org_id=org_id,
                description=er.description,
                severity=er.severity,
                category=er.category,
                is_blocker=er.is_blocker,
                confidence=er.confidence,
            )
            db.add(risk_obj)
            risk_objects.append(risk_obj)

        # Compute live execution score from ALL tasks in this meeting
        all_tasks_q = await db.execute(select(Task).where(Task.meeting_id == meeting_id))
        all_risks_q = await db.execute(select(Risk).where(Risk.meeting_id == meeting_id))
        all_tasks = list(all_tasks_q.scalars().all()) + task_objects
        all_risks = list(all_risks_q.scalars().all()) + risk_objects

        # Convert ORM → schema for scorer
        task_schemas = [
            ETSchema(
                description=t.description,
                assignee=t.assignee_name,
                deadline_raw=t.deadline_raw,
                is_vague=t.is_vague,
                confidence=t.confidence,
            )
            for t in all_tasks
        ]

        score_data = execution_scorer.compute(task_schemas, all_risks, meeting_id, org_id)
        db.add(ExecutionScore(
            id=uuid.uuid4(),
            meeting_id=meeting_id,
            org_id=org_id,
            score=score_data["score"],
            tasks_total=score_data["tasks_total"],
            tasks_with_owner=score_data["tasks_with_owner"],
            tasks_with_deadline=score_data["tasks_with_deadline"],
            vague_count=score_data["vague_count"],
            blocker_count=score_data["blocker_count"],
        ))

        await db.commit()

    # Publish extraction results to dashboard
    await publish_event(
        f"meeting:{meeting_id}:events",
        {
            "event_type": "extraction",
            "meeting_id": meeting_id,
            "data": {
                "tasks":     [t.model_dump() for t in result.tasks],
                "decisions": [d.model_dump() for d in result.decisions],
                "risks":     [r.model_dump() for r in result.risks],
                "topics":    result.topics,
                "score":     score_data,
            },
        }
    )

    # Dispatch graph update
    update_graph.apply_async(
        args=[meeting_id, org_id, result.model_dump_json()],
        queue="graph_update",
    )

    return {
        "status": "ok",
        "tasks": len(result.tasks),
        "decisions": len(result.decisions),
        "risks": len(result.risks),
    }


# ── Task 3: Graph Memory Update ───────────────────────────────────────────────

@celery_app.task(name="workers.pipeline_worker.update_graph")
def update_graph(meeting_id: str, org_id: str, result_json: str):
    return run_async(_update_graph_async(meeting_id, org_id, result_json))


async def _update_graph_async(meeting_id: str, org_id: str, result_json: str):
    from services.graph.neo4j_builder import graph_builder
    from models.schemas import ExtractionResult

    result = ExtractionResult.model_validate_json(result_json)

    for decision in result.decisions:
        await graph_builder.add_decision(
            decision_id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            org_id=org_id,
            description=decision.description,
            made_by=decision.made_by,
        )

    for task in result.tasks:
        await graph_builder.add_task(
            task_id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            org_id=org_id,
            description=task.description,
            assignee=task.assignee,
            deadline=task.deadline_raw,
            is_vague=task.is_vague,
        )

    for risk in result.risks:
        await graph_builder.add_risk(
            risk_id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            org_id=org_id,
            description=risk.description,
            is_blocker=risk.is_blocker,
        )

    if result.topics:
        await graph_builder.add_topics(meeting_id, result.topics)

    logger.info(
        "Graph updated",
        meeting_id=meeting_id,
        decisions=len(result.decisions),
        tasks=len(result.tasks),
        risks=len(result.risks),
    )
