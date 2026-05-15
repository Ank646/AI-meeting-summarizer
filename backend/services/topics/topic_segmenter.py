"""
Topic Segmentation Engine.

Problem:
  A 1-hour meeting covers many topics: hiring, product roadmap, budget, risks.
  Treating the whole transcript as one semantic unit makes retrieval imprecise:
  "Find all decisions about hiring" returns unrelated product decisions.

Solution:
  Use embedding-based cosine similarity to detect topic boundaries.
  When consecutive transcript chunks drift apart semantically, mark a topic break.
  Cluster transcript chunks into topic segments.
  Store topic nodes in Neo4j.

Algorithm:
  1. Embed each transcript chunk (already done for pgvector storage)
  2. Compute cosine similarity between consecutive chunks
  3. When similarity drops below threshold → topic boundary
  4. Extract topic label by prompting the LLM with that segment
  5. Update Neo4j: Meeting -[:TAGGED_WITH]-> Topic

Why this improves retrieval:
  ─ pgvector search within a topic segment is more precise
  ─ Graph query "show all decisions in the hiring topic" becomes trivial
  ─ Decision tracking: if the same topic recurs across meetings,
    graph traversal links all related decisions automatically
  ─ Agenda reconstruction: topics appear in order (natural meeting summary)
"""

import asyncio
from typing import List, Optional, Dict, Tuple
import numpy as np
import structlog
from core.config import settings

logger = structlog.get_logger()

# Cosine similarity below this threshold = topic boundary detected
BOUNDARY_THRESHOLD = 0.55

# Minimum consecutive chunks to form a valid topic segment
MIN_SEGMENT_CHUNKS = 2


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two embedding vectors."""
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 1.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def detect_topic_boundaries(
    embeddings: List[np.ndarray],
    threshold: float = BOUNDARY_THRESHOLD,
) -> List[int]:
    """
    Find indices where topic boundaries occur.
    A boundary at index i means chunks[i] and chunks[i+1] are in different topics.

    Algorithm:
      - Compare each pair of adjacent chunk embeddings
      - If cosine similarity < threshold → topic boundary
      - Returns indices of boundary positions (0-based)
    """
    if len(embeddings) < 2:
        return []

    boundaries = []
    for i in range(len(embeddings) - 1):
        sim = cosine_similarity(embeddings[i], embeddings[i + 1])
        if sim < threshold:
            boundaries.append(i)
            logger.debug("Topic boundary detected", position=i, similarity=round(sim, 3))

    return boundaries


def segment_by_boundaries(
    chunks: List[str],
    boundaries: List[int],
) -> List[List[str]]:
    """
    Split chunks into topic segments at boundary positions.
    Returns list of segments, each being a list of text chunks.
    """
    if not boundaries:
        return [chunks]

    segments = []
    start = 0
    for boundary in boundaries:
        segment = chunks[start: boundary + 1]
        if len(segment) >= MIN_SEGMENT_CHUNKS:
            segments.append(segment)
        start = boundary + 1

    # Last segment
    last = chunks[start:]
    if len(last) >= MIN_SEGMENT_CHUNKS:
        segments.append(last)

    return segments if segments else [chunks]


async def label_topic_segment(segment_text: str) -> str:
    """
    Use the LLM to generate a concise topic label for a transcript segment.
    Example output: "Q3 Product Roadmap" / "Engineering Hiring" / "Budget Review"
    """
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.0,
            num_predict=30,
        )
        prompt = (
            f"In 4 words or fewer, name the business topic of this meeting segment:\n\n"
            f"{segment_text[:800]}\n\nTopic name:"
        )
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        label = response.content.strip().strip('"').strip("'").split("\n")[0]
        return label[:60]   # cap length
    except Exception as e:
        logger.warning("Topic labeling failed", error=str(e))
        return "General Discussion"


async def segment_meeting_transcript(
    meeting_id: str,
    chunks: List[str],
    embeddings: List[np.ndarray],
) -> List[Dict]:
    """
    Full topic segmentation pipeline for a complete meeting transcript.

    Returns list of topic segments:
    [
      {"label": "Q3 Planning", "chunks": [...], "start_chunk": 0, "end_chunk": 4},
      {"label": "Hiring Discussion", "chunks": [...], "start_chunk": 5, "end_chunk": 9},
    ]
    """
    if not chunks or not embeddings:
        return []

    # Detect boundaries
    boundaries = detect_topic_boundaries(embeddings)
    chunk_groups = segment_by_boundaries(chunks, boundaries)

    segments = []
    chunk_cursor = 0

    for group in chunk_groups:
        segment_text = " ".join(group)
        label = await label_topic_segment(segment_text)

        segments.append({
            "label":       label,
            "chunks":      group,
            "chunk_text":  segment_text[:500],
            "start_chunk": chunk_cursor,
            "end_chunk":   chunk_cursor + len(group) - 1,
            "chunk_count": len(group),
        })
        chunk_cursor += len(group)

    logger.info("Meeting segmented", meeting_id=meeting_id, segments=len(segments))
    return segments


async def store_segments_in_graph(
    meeting_id: str,
    org_id: str,
    segments: List[Dict],
):
    """
    Store topic segments as Topic nodes in Neo4j.
    Each segment becomes a Topic node linked to the Meeting and tagged with
    start/end chunk indices for retrieval alignment.
    """
    from services.graph.neo4j_builder import graph_builder

    for seg in segments:
        # Add as topic (graph_builder MERGE ensures dedup by name)
        await graph_builder.add_topics(meeting_id, [seg["label"]])

        # Update topic node with segment metadata
        driver = await graph_builder._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MATCH (m:Meeting {id: $meeting_id})-[:TAGGED_WITH]->(tp:Topic {name: $name})
                SET tp.start_chunk = $start,
                    tp.end_chunk   = $end,
                    tp.chunk_count = $count,
                    tp.preview     = $preview
                """,
                meeting_id=meeting_id,
                name=seg["label"].lower().strip(),
                start=seg["start_chunk"],
                end=seg["end_chunk"],
                count=seg["chunk_count"],
                preview=seg["chunk_text"][:200],
            )

    logger.info("Topic segments stored in graph", meeting_id=meeting_id)


async def get_topic_for_chunk(
    meeting_id: str, chunk_index: int
) -> Optional[str]:
    """
    Query Neo4j to find which topic segment a given chunk belongs to.
    Used for topic-aware retrieval (search within a topic).
    """
    from services.graph.neo4j_builder import graph_builder
    driver = await graph_builder._get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Meeting {id: $meeting_id})-[:TAGGED_WITH]->(tp:Topic)
            WHERE tp.start_chunk <= $idx AND tp.end_chunk >= $idx
            RETURN tp.name AS topic
            LIMIT 1
            """,
            meeting_id=meeting_id, idx=chunk_index,
        )
        record = await result.single()
        return record["topic"] if record else None
