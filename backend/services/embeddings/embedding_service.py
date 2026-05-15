"""
Semantic embedding service using sentence-transformers (BGE-large).

Embeddings are stored in PostgreSQL via the pgvector extension.
Used for semantic transcript search (vector RAG).

Search uses cosine distance: lower distance = higher similarity.
We return 1 - distance as the similarity score so higher = better.
"""

import asyncio
from typing import List, Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
from core.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """Lazy-loaded singleton sentence-transformers model."""

    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model", model=settings.embedding_model)
        device = "cuda" if settings.whisper_device == "cuda" else "cpu"
        self._model = SentenceTransformer(
            settings.embedding_model,
            device=device,
            cache_folder="/root/.cache/sentence_transformers",
        )
        logger.info("Embedding model loaded")

    async def embed(self, texts: List[str]) -> np.ndarray:
        """Encode a batch of texts, return normalized float32 embeddings."""
        self._load_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        )
        return embeddings

    async def embed_single(self, text: str) -> List[float]:
        """Embed one text, return as Python list (for pgvector storage)."""
        embeddings = await self.embed([text])
        return embeddings[0].tolist()

    async def search_similar(
        self,
        db: AsyncSession,
        query: str,
        org_id: str,
        top_k: int = 10,
        meeting_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Cosine similarity search over stable transcript embeddings in pgvector.

        Uses HNSW index (created in init.sql) for approximate nearest neighbor search.
        Returns top_k most similar chunks with metadata.
        """
        query_vec = await self.embed_single(query)
        # pgvector expects a string like "[0.1, 0.2, ...]"
        vec_str = "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]"

        meeting_clause = "AND t.meeting_id = :meeting_id" if meeting_id else ""

        sql = text(f"""
            SELECT
                t.id::text                              AS id,
                t.meeting_id::text                      AS meeting_id,
                t.text                                  AS text,
                t.speaker_name                          AS speaker_name,
                t.start_time                            AS start_time,
                m.title                                 AS meeting_title,
                m.created_at                            AS meeting_date,
                1 - (t.embedding <=> :vec::vector)      AS similarity
            FROM transcripts t
            JOIN meetings m ON t.meeting_id = m.id
            WHERE t.org_id   = :org_id
              AND t.is_stable = TRUE
              AND t.embedding IS NOT NULL
              {meeting_clause}
            ORDER BY t.embedding <=> :vec::vector
            LIMIT :top_k
        """)

        params: dict = {"vec": vec_str, "org_id": org_id, "top_k": top_k}
        if meeting_id:
            params["meeting_id"] = meeting_id

        result = await db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": row.id,
                "meeting_id": row.meeting_id,
                "text": row.text,
                "speaker_name": row.speaker_name,
                "start_time": row.start_time,
                "meeting_title": row.meeting_title,
                "meeting_date": row.meeting_date.isoformat() if row.meeting_date else None,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]


# Module-level singleton
embedding_service = EmbeddingService()
