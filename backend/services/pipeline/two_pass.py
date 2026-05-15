"""
Two-Pass Intelligence Pipeline.

PASS 1 — Real-Time (Live during meeting)
  Goal: Low latency, tentative insights
  Trade-off: ~chunk-level accuracy, may have diarization artifacts

  Pipeline:
    audio stream → VAD → 10s chunks → Whisper → pyannote →
    rolling context buffer → fast LLM extraction →
    tentative tasks/decisions/risks → live dashboard

  Latency target: < 8 seconds from speech to dashboard update

PASS 2 — Post-Meeting Refinement (After meeting ends)
  Goal: High accuracy, production-quality results
  Trade-off: Not real-time, runs as a batch job

  Pipeline:
    full audio file (MinIO) →
    Whisper large-v3 (full file, no chunking) →
    pyannote (full audio, better speaker consistency) →
    topic segmentation (full transcript view) →
    deep LLM extraction (full context window) →
    graph reconciliation (replace tentative with refined) →
    notify dashboard

  Why Pass 2 improves accuracy:
    ─ Full-file Whisper eliminates chunking artifacts (words cut at boundaries)
    ─ Full-file diarization has consistent speaker IDs (no cross-chunk drift)
    ─ LLM sees the complete meeting context → catches decisions spanning multiple topics
    ─ Self-consistency check runs on the full transcript (not 30s windows)
    ─ Topic segmentation only works accurately on the complete transcript
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
import structlog
from core.config import settings

logger = structlog.get_logger()


class TwoPassPipeline:

    async def run_pass2(self, meeting_id: str, org_id: str) -> dict:
        """
        Trigger full post-meeting refinement.
        Called automatically when a meeting ends (via /meetings/{id}/end endpoint).

        Steps:
          1. Download full audio from MinIO
          2. Run full-file Whisper ASR
          3. Run full-file diarization
          4. Build complete transcript
          5. Run topic segmentation
          6. Run deep LLM extraction with full context
          7. Reconcile with existing tentative data in PostgreSQL
          8. Update Neo4j graph with refined data
          9. Broadcast refinement complete event
        """
        logger.info("Pass 2 starting", meeting_id=meeting_id)

        # Step 1 — fetch audio
        audio = await self._fetch_audio(meeting_id, org_id)
        if audio is None:
            logger.warning("Pass 2 skipped — no audio found", meeting_id=meeting_id)
            return {"status": "skipped", "reason": "no_audio"}

        # Step 2 — full-file Whisper ASR
        from services.asr.whisper_service import whisper_service
        asr_segments = await whisper_service.transcribe_chunk(audio, language="en")

        if not asr_segments:
            return {"status": "skipped", "reason": "no_transcript"}

        full_text = " ".join(s.text for s in asr_segments)
        all_words = [
            {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
            for seg in asr_segments for w in seg.words
        ]

        # Step 3 — full-file diarization
        from services.diarization.diarizer import diarizer
        speaker_segments = await diarizer.diarize(audio)
        diarized_words = diarizer.align_words_to_speakers(all_words, speaker_segments)
        utterances = diarizer.group_by_speaker(diarized_words)

        # Step 4 — embed all chunks for topic segmentation
        from services.embeddings.embedding_service import embedding_service
        import numpy as np

        chunk_size = 500  # characters per chunk
        text_chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        if not text_chunks:
            return {"status": "skipped", "reason": "empty_transcript"}

        embeddings_raw = await embedding_service.embed(text_chunks)
        embeddings = [np.array(e) for e in embeddings_raw]

        # Step 5 — topic segmentation (full view)
        from services.topics.topic_segmenter import (
            segment_meeting_transcript, store_segments_in_graph
        )
        segments = await segment_meeting_transcript(meeting_id, text_chunks, embeddings)
        await store_segments_in_graph(meeting_id, org_id, segments)

        # Step 6 — deep LLM extraction with full context
        from services.context.context_buffer import build_extraction_context
        from services.extraction.llm_extractor import llm_extractor

        speaker_ctx = "\n".join(f"{u['speaker']}: {u['text'][:100]}" for u in utterances[:10])
        ctx = await build_extraction_context(meeting_id, full_text)
        refined_result = await llm_extractor.extract(
            ctx["context_window"] or full_text,
            speaker_context=speaker_ctx,
        )

        # Step 7 — reconcile refined results with PostgreSQL
        refined_counts = await self._reconcile_results(
            meeting_id, org_id, refined_result, utterances, full_text, embeddings_raw
        )

        # Step 8 — update graph with refined data
        from services.graph.neo4j_builder import graph_builder
        for dec in refined_result.decisions:
            await graph_builder.add_decision(
                str(uuid.uuid4()), meeting_id, org_id,
                dec.description, made_by=dec.made_by
            )
        for task in refined_result.tasks:
            await graph_builder.add_task(
                str(uuid.uuid4()), meeting_id, org_id,
                task.description, assignee=task.assignee,
                deadline=task.deadline_raw, is_vague=task.is_vague
            )

        # Step 9 — broadcast refinement complete
        from core.redis_client import publish_event
        await publish_event(
            f"meeting:{meeting_id}:events",
            {
                "event_type": "pass2_complete",
                "meeting_id": meeting_id,
                "data": {
                    "refined_tasks":      len(refined_result.tasks),
                    "refined_decisions":  len(refined_result.decisions),
                    "refined_risks":      len(refined_result.risks),
                    "topics":             [s["label"] for s in segments],
                    "message": "Post-meeting analysis complete. Results refined.",
                },
            }
        )

        logger.info("Pass 2 complete", meeting_id=meeting_id, **refined_counts)
        return {"status": "ok", **refined_counts}

    async def _fetch_audio(
        self, meeting_id: str, org_id: str
    ) -> Optional["np.ndarray"]:
        """Download audio from MinIO and convert to numpy array."""
        try:
            from minio import Minio
            import io, numpy as np, soundfile as sf
            client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_root_user,
                secret_key=settings.minio_root_password,
                secure=settings.minio_secure,
            )
            object_path = f"{org_id}/{meeting_id}/audio.wav"
            response = client.get_object(settings.minio_bucket, object_path)
            data = response.read()
            audio, _ = sf.read(io.BytesIO(data), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            return audio
        except Exception as e:
            logger.error("Failed to fetch audio from MinIO", error=str(e))
            return None

    async def _reconcile_results(
        self,
        meeting_id: str,
        org_id: str,
        refined_result,
        utterances: list,
        full_text: str,
        embeddings,
    ) -> dict:
        """
        Replace tentative Pass 1 results with refined Pass 2 results.

        Strategy:
          - Delete low-confidence tentative items (confidence < 0.6)
          - Upsert refined items (keep tentative if no refined equivalent)
          - Recompute execution score with refined data
        """
        from core.database import AsyncSessionLocal
        from models.db_models import Task, Decision, Risk, Transcript, ExecutionScore
        from models.schemas import ExtractedTask as ETSchema
        from services.scoring.execution_scorer import execution_scorer
        from services.extraction.scorer import normalize_deadline
        from sqlalchemy import delete, select
        import numpy as np

        async with AsyncSessionLocal() as db:
            # Remove tentative low-confidence items
            await db.execute(
                delete(Task).where(
                    Task.meeting_id == meeting_id,
                    Task.confidence < 0.6,
                )
            )
            await db.execute(
                delete(Decision).where(
                    Decision.meeting_id == meeting_id,
                    Decision.confidence < 0.6,
                )
            )

            # Insert refined items
            for et in refined_result.tasks:
                db.add(Task(
                    id=uuid.uuid4(), meeting_id=meeting_id, org_id=org_id,
                    description=et.description, assignee_name=et.assignee,
                    deadline_raw=et.deadline_raw,
                    deadline_iso=normalize_deadline(et.deadline_raw),
                    confidence=et.confidence, is_vague=et.is_vague,
                ))
            for ed in refined_result.decisions:
                db.add(Decision(
                    id=uuid.uuid4(), meeting_id=meeting_id, org_id=org_id,
                    description=ed.description, made_by=ed.made_by,
                    rationale=ed.rationale, confidence=ed.confidence,
                ))

            # Recompute execution score
            all_tasks_q = await db.execute(
                select(Task).where(Task.meeting_id == meeting_id)
            )
            all_risks_q = await db.execute(
                select(Risk).where(Risk.meeting_id == meeting_id)
            )
            all_tasks = all_tasks_q.scalars().all()
            all_risks = all_risks_q.scalars().all()

            task_schemas = [
                ETSchema(
                    description=t.description, assignee=t.assignee_name,
                    deadline_raw=t.deadline_raw, is_vague=t.is_vague,
                    confidence=t.confidence,
                )
                for t in all_tasks
            ]
            score_data = execution_scorer.compute(task_schemas, all_risks, meeting_id, org_id)
            db.add(ExecutionScore(
                id=uuid.uuid4(), meeting_id=meeting_id, org_id=org_id,
                score=score_data["score"],
                tasks_total=score_data["tasks_total"],
                tasks_with_owner=score_data["tasks_with_owner"],
                tasks_with_deadline=score_data["tasks_with_deadline"],
                vague_count=score_data["vague_count"],
                blocker_count=score_data["blocker_count"],
            ))
            await db.commit()

        return {
            "tasks_refined":     len(refined_result.tasks),
            "decisions_refined": len(refined_result.decisions),
            "risks_refined":     len(refined_result.risks),
        }


# Module-level singleton
two_pass_pipeline = TwoPassPipeline()
