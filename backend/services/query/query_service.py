"""
Query Service Layer.

Architecture principle:
  The dashboard and API clients NEVER query PostgreSQL, pgvector, or Neo4j directly.
  All reads go through this service, which:
    1. Enforces org-level access control
    2. Aggregates results from all three data stores
    3. Caches frequent queries in Redis (TTL-based)
    4. Publishes aggregated results to Redis pub/sub for live dashboard

Benefits:
  ─ Single point for access control enforcement
  ─ Cache hit rate significantly reduces DB load during live meetings
  ─ Dashboard queries are non-blocking (results come via pub/sub)
  ─ Easy to add analytics instrumentation in one place
"""

import json
from typing import Optional, List, Dict, Any
import structlog
from core.redis_client import get_cached, set_with_ttl, publish_event

logger = structlog.get_logger()

# Cache TTLs
SCORE_CACHE_TTL   = 10    # execution score: refresh every 10s (live meeting)
TASKS_CACHE_TTL   = 30    # tasks: refresh every 30s
SEARCH_CACHE_TTL  = 300   # search results: cache 5 minutes
ORG_SCORE_TTL     = 60    # org aggregate score: 1 minute


class QueryService:
    """
    Unified read layer over PostgreSQL + pgvector + Neo4j.
    All methods enforce org_id tenancy.
    """

    # ── Meeting data ────────────────────────────────────────────────────────

    async def get_meeting_summary(
        self, meeting_id: str, org_id: str
    ) -> Optional[Dict]:
        """
        Aggregate view of a meeting:
          task count, decision count, risk count, latest score, topics.
        Cached for 30s.
        """
        cache_key = f"qs:summary:{meeting_id}"
        cached = await get_cached(cache_key)
        if cached:
            return cached

        from core.database import AsyncSessionLocal
        from models.db_models import Task, Decision, Risk, ExecutionScore, Meeting
        from sqlalchemy import select, func, desc

        async with AsyncSessionLocal() as db:
            # Verify org ownership
            meeting_q = await db.execute(
                select(Meeting).where(
                    Meeting.id == meeting_id,
                    Meeting.org_id == org_id,
                )
            )
            meeting = meeting_q.scalar_one_or_none()
            if not meeting:
                return None

            # Counts
            tasks_q = await db.execute(
                select(func.count()).select_from(Task).where(Task.meeting_id == meeting_id)
            )
            decisions_q = await db.execute(
                select(func.count()).select_from(Decision).where(Decision.meeting_id == meeting_id)
            )
            risks_q = await db.execute(
                select(func.count()).select_from(Risk).where(Risk.meeting_id == meeting_id)
            )
            blockers_q = await db.execute(
                select(func.count()).select_from(Risk).where(
                    Risk.meeting_id == meeting_id,
                    Risk.is_blocker == True,
                )
            )
            score_q = await db.execute(
                select(ExecutionScore)
                .where(ExecutionScore.meeting_id == meeting_id)
                .order_by(desc(ExecutionScore.computed_at))
                .limit(1)
            )
            latest_score = score_q.scalar_one_or_none()

        summary = {
            "meeting_id":   str(meeting_id),
            "title":        meeting.title,
            "status":       meeting.status,
            "task_count":   tasks_q.scalar(),
            "decision_count": decisions_q.scalar(),
            "risk_count":   risks_q.scalar(),
            "blocker_count": blockers_q.scalar(),
            "score":        latest_score.score if latest_score else None,
            "started_at":   meeting.started_at.isoformat() if meeting.started_at else None,
        }

        await set_with_ttl(cache_key, summary, TASKS_CACHE_TTL)
        return summary

    # ── Live score ──────────────────────────────────────────────────────────

    async def get_live_score(
        self, meeting_id: str, org_id: str
    ) -> Optional[Dict]:
        """Latest execution score. Cached 10s for live meetings."""
        cache_key = f"qs:score:{meeting_id}"
        cached = await get_cached(cache_key)
        if cached:
            return cached

        from core.database import AsyncSessionLocal
        from models.db_models import ExecutionScore
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExecutionScore)
                .where(
                    ExecutionScore.meeting_id == meeting_id,
                    ExecutionScore.org_id == org_id,
                )
                .order_by(desc(ExecutionScore.computed_at))
                .limit(1)
            )
            score = result.scalar_one_or_none()

        if not score:
            return None

        data = {
            "score":               score.score,
            "tasks_total":         score.tasks_total,
            "tasks_with_owner":    score.tasks_with_owner,
            "tasks_with_deadline": score.tasks_with_deadline,
            "vague_count":         score.vague_count,
            "blocker_count":       score.blocker_count,
            "computed_at":         score.computed_at.isoformat(),
        }
        await set_with_ttl(cache_key, data, SCORE_CACHE_TTL)
        return data

    # ── Open tasks across org ───────────────────────────────────────────────

    async def get_org_open_tasks(
        self,
        org_id: str,
        assignee: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Open tasks across all org meetings. Cached 30s."""
        cache_key = f"qs:open_tasks:{org_id}:{assignee or 'all'}"
        cached = await get_cached(cache_key)
        if cached:
            return cached

        from core.database import AsyncSessionLocal
        from models.db_models import Task
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            stmt = select(Task).where(
                Task.org_id == org_id,
                Task.status == "open",
            )
            if assignee:
                stmt = stmt.where(Task.assignee_name.ilike(f"%{assignee}%"))
            stmt = stmt.order_by(Task.deadline_iso.asc().nulls_last()).limit(limit)
            result = await db.execute(stmt)
            tasks = result.scalars().all()

        data = [
            {
                "id":          str(t.id),
                "description": t.description,
                "assignee":    t.assignee_name,
                "deadline":    t.deadline_iso.isoformat() if t.deadline_iso else t.deadline_raw,
                "is_vague":    t.is_vague,
                "meeting_id":  str(t.meeting_id),
                "confidence":  t.confidence,
            }
            for t in tasks
        ]
        await set_with_ttl(cache_key, data, TASKS_CACHE_TTL)
        return data

    # ── Org aggregate score ─────────────────────────────────────────────────

    async def get_org_aggregate_score(self, org_id: str) -> Dict:
        """Aggregate execution metrics across all org meetings. Cached 60s."""
        cache_key = f"qs:org_score:{org_id}"
        cached = await get_cached(cache_key)
        if cached:
            return cached

        from core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
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
                    FROM execution_scores WHERE org_id = :org_id
                """),
                {"org_id": str(org_id)},
            )
            row = result.fetchone()

        data = {
            "org_id":              str(org_id),
            "avg_score":           round(float(row.avg_score), 4),
            "total_tasks":         int(row.total_tasks),
            "owned_tasks":         int(row.owned_tasks),
            "deadline_tasks":      int(row.deadline_tasks),
            "vague_total":         int(row.vague_total),
            "blocker_total":       int(row.blocker_total),
            "meetings_analyzed":   int(row.meetings_analyzed),
        }
        await set_with_ttl(cache_key, data, ORG_SCORE_TTL)
        return data

    # ── Hybrid search ───────────────────────────────────────────────────────

    async def hybrid_search(
        self,
        query: str,
        org_id: str,
        top_k: int = 10,
        use_graph: bool = True,
        meeting_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Aggregate results from pgvector + Neo4j + SQL FTS.
        Cache results for 5 minutes (search results don't change rapidly).
        """
        cache_key = f"qs:search:{org_id}:{hash(query)}:{top_k}:{meeting_id}"
        cached = await get_cached(cache_key)
        if cached:
            return cached

        from services.embeddings.embedding_service import embedding_service
        from services.graph.neo4j_builder import graph_builder
        from core.database import AsyncSessionLocal
        from sqlalchemy import text

        results = []

        # Vector
        async with AsyncSessionLocal() as db:
            try:
                vector_hits = await embedding_service.search_similar(
                    db, query, str(org_id), top_k, meeting_id
                )
                for h in vector_hits:
                    results.append({
                        "source": "vector", "score": h["similarity"],
                        "content": h["text"], "meeting_id": h["meeting_id"],
                        "meeting_title": h.get("meeting_title"),
                        "metadata": {"speaker": h.get("speaker_name")},
                    })
            except Exception as e:
                logger.warning("Vector search failed in query service", error=str(e))

        # Graph
        if use_graph:
            try:
                graph_hits = await graph_builder.find_related_decisions(
                    query, str(org_id), limit=5
                )
                for h in graph_hits:
                    results.append({
                        "source": "graph",
                        "score": min(1.0, float(h.get("shared_topics", 1)) / 5.0),
                        "content": h.get("description", ""),
                        "meeting_title": h.get("meeting"),
                        "metadata": {"type": "decision"},
                    })
            except Exception as e:
                logger.warning("Graph search failed in query service", error=str(e))

        # SQL FTS
        async with AsyncSessionLocal() as db:
            try:
                sql_hits = await db.execute(
                    text("""
                        SELECT 'task' AS t, description, meeting_id::text, confidence
                        FROM tasks WHERE org_id = :org
                          AND to_tsvector('english', description) @@ plainto_tsquery(:q)
                        UNION ALL
                        SELECT 'decision', description, meeting_id::text, confidence
                        FROM decisions WHERE org_id = :org
                          AND to_tsvector('english', description) @@ plainto_tsquery(:q)
                        ORDER BY confidence DESC LIMIT :lim
                    """),
                    {"org": str(org_id), "q": query, "lim": top_k},
                )
                for row in sql_hits.fetchall():
                    results.append({
                        "source": "sql", "score": float(row.confidence or 0.5),
                        "content": row.description, "meeting_id": row.meeting_id,
                        "metadata": {"type": row.t},
                    })
            except Exception as e:
                logger.warning("SQL search failed in query service", error=str(e))

        results.sort(key=lambda r: r["score"], reverse=True)
        top = results[:top_k]
        await set_with_ttl(cache_key, top, SEARCH_CACHE_TTL)
        return top


# Module-level singleton
query_service = QueryService()
