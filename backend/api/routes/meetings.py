from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from uuid import UUID
import uuid
import base64
import structlog

from core.database import get_db
from api.deps import get_current_user
from models.db_models import Meeting, Task, Decision, Risk, ExecutionScore, MeetingStatus
from models.schemas import MeetingCreate, MeetingOut, ExecutionScoreOut
from services.graph.neo4j_builder import graph_builder

router = APIRouter(prefix="/meetings", tags=["meetings"])
logger = structlog.get_logger()


@router.post("/", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new meeting and register it in the graph."""
    meeting = Meeting(
        id=uuid.uuid4(),
        org_id=payload.org_id,
        title=payload.title,
        status=MeetingStatus.SCHEDULED,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    # Register in Neo4j
    await graph_builder.upsert_meeting(
        str(meeting.id), str(meeting.org_id), meeting.title
    )

    return meeting


@router.post("/{meeting_id}/start")
async def start_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(db, meeting_id)
    from datetime import datetime
    meeting.status = MeetingStatus.LIVE
    meeting.started_at = datetime.utcnow()
    await db.commit()
    return {"status": "live", "meeting_id": str(meeting_id)}


@router.post("/{meeting_id}/end")
async def end_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    meeting = await _get_meeting_or_404(db, meeting_id)
    from datetime import datetime
    meeting.status = MeetingStatus.COMPLETED
    meeting.ended_at = datetime.utcnow()
    await db.commit()
    return {"status": "completed", "meeting_id": str(meeting_id)}


@router.post("/{meeting_id}/upload")
async def upload_audio(
    meeting_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload a complete audio file for batch processing via Celery."""
    from minio import Minio
    from core.config import settings
    import io

    meeting = await _get_meeting_or_404(db, meeting_id)
    audio_bytes = await file.read()

    # Store raw audio in MinIO
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)

    object_path = f"{meeting.org_id}/{meeting_id}/audio.wav"
    client.put_object(
        settings.minio_bucket,
        object_path,
        io.BytesIO(audio_bytes),
        length=len(audio_bytes),
        content_type=file.content_type or "audio/wav",
    )

    meeting.audio_path = object_path
    meeting.status = MeetingStatus.PROCESSING
    await db.commit()

    background_tasks.add_task(
        _dispatch_audio_file,
        audio_bytes=audio_bytes,
        meeting_id=str(meeting_id),
        org_id=str(meeting.org_id),
    )

    return {"status": "processing", "object_path": object_path}


async def _dispatch_audio_file(audio_bytes: bytes, meeting_id: str, org_id: str):
    """Split a full audio file into sliding-window chunks and enqueue to Celery."""
    from workers.pipeline_worker import process_audio_chunk

    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2   # int16
    CHUNK_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 10   # 10 seconds
    STRIDE_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 8   # 8 seconds

    chunk_index = 0
    for offset in range(0, len(audio_bytes) - CHUNK_BYTES + 1, STRIDE_BYTES):
        chunk = audio_bytes[offset: offset + CHUNK_BYTES]
        if len(chunk) < SAMPLE_RATE * BYTES_PER_SAMPLE:  # skip < 1s tail
            break
        encoded = base64.b64encode(chunk).decode()
        process_audio_chunk.apply_async(
            args=[meeting_id, org_id, encoded, chunk_index, chunk_index * 8.0, False],
            queue="audio_pipeline",
        )
        chunk_index += 1


@router.get("/{meeting_id}/transcript")
async def get_transcript(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from models.db_models import Transcript
    result = await db.execute(
        select(Transcript)
        .where(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.start_time)
    )
    transcripts = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "speaker": t.speaker_name or t.speaker_label or "UNKNOWN",
            "text": t.text,
            "start": t.start_time,
            "end": t.end_time,
            "is_stable": t.is_stable,
            "confidence": t.confidence,
        }
        for t in transcripts
    ]


@router.get("/{meeting_id}/tasks")
async def get_tasks(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.meeting_id == meeting_id)
        .order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "description": t.description,
            "assignee": t.assignee_name,
            "deadline_raw": t.deadline_raw,
            "deadline_iso": t.deadline_iso.isoformat() if t.deadline_iso else None,
            "status": t.status,
            "is_vague": t.is_vague,
            "confidence": t.confidence,
        }
        for t in tasks
    ]


@router.get("/{meeting_id}/decisions")
async def get_decisions(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Decision)
        .where(Decision.meeting_id == meeting_id)
        .order_by(Decision.created_at)
    )
    decisions = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "description": d.description,
            "made_by": d.made_by,
            "rationale": d.rationale,
            "confidence": d.confidence,
        }
        for d in decisions
    ]


@router.get("/{meeting_id}/risks")
async def get_risks(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Risk)
        .where(Risk.meeting_id == meeting_id)
        .order_by(Risk.created_at)
    )
    risks = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "description": r.description,
            "severity": r.severity,
            "category": r.category,
            "is_blocker": r.is_blocker,
            "confidence": r.confidence,
        }
        for r in risks
    ]


@router.get("/{meeting_id}/score", response_model=ExecutionScoreOut)
async def get_execution_score(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(ExecutionScore)
        .where(ExecutionScore.meeting_id == meeting_id)
        .order_by(desc(ExecutionScore.computed_at))
        .limit(1)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Score not yet computed for this meeting")
    return score


async def _get_meeting_or_404(db: AsyncSession, meeting_id: UUID) -> Meeting:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting
