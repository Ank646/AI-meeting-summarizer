from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import Optional

from core.database import get_db
from api.deps import get_current_user
from models.db_models import Meeting, Task, ExecutionScore

router = APIRouter(prefix="/org", tags=["analytics"])


@router.get("/execution-score")
async def org_execution_score(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Aggregate execution intelligence across all meetings for an org."""
    result = await db.execute(
        text("""
            SELECT
                COALESCE(AVG(score), 0)               AS avg_score,
                COALESCE(SUM(tasks_total), 0)          AS total_tasks,
                COALESCE(SUM(tasks_with_owner), 0)     AS owned_tasks,
                COALESCE(SUM(tasks_with_deadline), 0)  AS deadline_tasks,
                COALESCE(SUM(vague_count), 0)          AS vague_total,
                COALESCE(SUM(blocker_count), 0)        AS blocker_total,
                COUNT(DISTINCT meeting_id)             AS meetings_analyzed
            FROM execution_scores
            WHERE org_id = :org_id
        """),
        {"org_id": str(org_id)},
    )
    row = result.fetchone()
    return {
        "org_id": str(org_id),
        "avg_execution_score": round(float(row.avg_score), 4),
        "total_tasks": int(row.total_tasks),
        "owned_tasks": int(row.owned_tasks),
        "deadline_tasks": int(row.deadline_tasks),
        "vague_commitments": int(row.vague_total),
        "blockers": int(row.blocker_total),
        "meetings_analyzed": int(row.meetings_analyzed),
    }


@router.get("/meetings")
async def list_meetings(
    org_id: UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all meetings for an org, newest first."""
    result = await db.execute(
        select(Meeting)
        .where(Meeting.org_id == org_id)
        .order_by(Meeting.created_at.desc())
        .limit(limit)
    )
    meetings = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "title": m.title,
            "status": m.status,
            "started_at": m.started_at.isoformat() if m.started_at else None,
            "ended_at": m.ended_at.isoformat() if m.ended_at else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in meetings
    ]


@router.get("/tasks/open")
async def open_tasks(
    org_id: UUID,
    assignee: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All open tasks across all meetings. Optionally filter by assignee."""
    stmt = select(Task).where(
        Task.org_id == org_id,
        Task.status == "open",
    )
    if assignee:
        stmt = stmt.where(Task.assignee_name.ilike(f"%{assignee}%"))
    stmt = stmt.order_by(Task.deadline_iso.asc().nulls_last(), Task.created_at.asc())

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "description": t.description,
            "assignee": t.assignee_name,
            "deadline": t.deadline_iso.isoformat() if t.deadline_iso else t.deadline_raw,
            "meeting_id": str(t.meeting_id),
            "is_vague": t.is_vague,
            "confidence": t.confidence,
        }
        for t in tasks
    ]


@router.get("/graph/decision-evolution")
async def decision_evolution(
    org_id: UUID,
    keyword: str = Query(..., description="Topic keyword to trace"),
    current_user=Depends(get_current_user),
):
    """Trace how decisions around a keyword evolved across meetings via graph."""
    from services.graph.neo4j_builder import graph_builder
    chain = await graph_builder.get_decision_evolution(keyword, str(org_id))
    return chain


@router.get("/graph/task-dependencies")
async def task_dependencies(
    org_id: UUID,
    current_user=Depends(get_current_user),
):
    """Return all task dependency edges for the org's dependency graph."""
    from services.graph.neo4j_builder import graph_builder
    deps = await graph_builder.get_task_dependencies(str(org_id))
    return deps


@router.get("/graph/user-blockers")
async def user_blockers(
    org_id: UUID,
    user_name: str = Query(...),
    current_user=Depends(get_current_user),
):
    """All blockers affecting a specific user's tasks."""
    from services.graph.neo4j_builder import graph_builder
    blockers = await graph_builder.get_blockers_for_user(user_name, str(org_id))
    return blockers
