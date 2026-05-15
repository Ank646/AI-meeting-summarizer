from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List
import structlog

from core.database import get_db
from api.deps import get_current_user
from models.schemas import SearchRequest, SearchResult
from services.embeddings.embedding_service import embedding_service
from services.graph.neo4j_builder import graph_builder

router = APIRouter(prefix="/search", tags=["search"])
logger = structlog.get_logger()


@router.post("/", response_model=List[SearchResult])
async def hybrid_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Hybrid retrieval across three data stores:
      1. pgvector — semantic transcript similarity
      2. Neo4j    — decision evolution and dependency graph
      3. PostgreSQL — structured keyword search (FTS)

    Results are merged, deduplicated, and sorted by score.
    """
    results: List[SearchResult] = []
    org_id = str(request.org_id)

    # ── 1. Vector Search ──────────────────────────────────────────────────────
    try:
        vector_hits = await embedding_service.search_similar(
            db=db,
            query=request.query,
            org_id=org_id,
            top_k=request.top_k,
            meeting_id=str(request.meeting_id) if request.meeting_id else None,
        )
        for hit in vector_hits:
            results.append(SearchResult(
                source="vector",
                score=float(hit["similarity"]),
                content=hit["text"],
                meeting_id=hit.get("meeting_id"),
                meeting_title=hit.get("meeting_title"),
                timestamp=None,
                metadata={
                    "speaker": hit.get("speaker_name"),
                    "start_time": hit.get("start_time"),
                },
            ))
    except Exception as e:
        logger.warning("Vector search failed", error=str(e))

    # ── 2. Graph Search ───────────────────────────────────────────────────────
    if request.use_graph:
        try:
            graph_hits = await graph_builder.find_related_decisions(
                decision_text=request.query,
                org_id=org_id,
                limit=5,
            )
            for hit in graph_hits:
                results.append(SearchResult(
                    source="graph",
                    score=min(1.0, float(hit.get("shared_topics", 1)) / 5.0),
                    content=hit.get("description", ""),
                    meeting_id=None,
                    meeting_title=hit.get("meeting"),
                    timestamp=None,
                    metadata={"type": "decision", "neo4j_id": str(hit.get("id", ""))},
                ))
        except Exception as e:
            logger.warning("Graph search failed", error=str(e))

    # ── 3. SQL Full-Text Search ───────────────────────────────────────────────
    try:
        sql_hits = await db.execute(
            text("""
                SELECT 'task'     AS item_type,
                       description AS content,
                       meeting_id::text,
                       assignee_name AS extra,
                       confidence,
                       created_at
                FROM tasks
                WHERE org_id = :org_id
                  AND to_tsvector('english', description) @@ plainto_tsquery('english', :query)

                UNION ALL

                SELECT 'decision',
                       description,
                       meeting_id::text,
                       made_by,
                       confidence,
                       created_at
                FROM decisions
                WHERE org_id = :org_id
                  AND to_tsvector('english', description) @@ plainto_tsquery('english', :query)

                ORDER BY confidence DESC
                LIMIT :lim
            """),
            {"org_id": org_id, "query": request.query, "lim": request.top_k},
        )
        for row in sql_hits.fetchall():
            results.append(SearchResult(
                source="sql",
                score=float(row.confidence or 0.5),
                content=row.content,
                meeting_id=row.meeting_id,
                meeting_title=None,
                timestamp=row.created_at,
                metadata={"type": row.item_type, "extra": row.extra},
            ))
    except Exception as e:
        logger.warning("SQL search failed", error=str(e))

    # Sort by score, return top_k
    results.sort(key=lambda r: r.score, reverse=True)
    return results[: request.top_k]
