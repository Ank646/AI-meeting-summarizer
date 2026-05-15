"""
Neo4j Graph Memory System.

Node types:  Meeting, User, Decision, Task, Risk, Topic
Edge types:  DISCUSSED_IN, ASSIGNED_TO, MADE_BY, REVISES,
             BLOCKS, DEPENDS_ON, TAGGED_WITH

The graph captures:
  - Which decisions were made in which meetings
  - How decisions evolved over time (REVISES chain)
  - Who owns which tasks (ASSIGNED_TO)
  - Task dependencies (DEPENDS_ON)
  - What blocked what (BLOCKS)
  - Shared topics across meetings (TAGGED_WITH)
"""

from typing import Optional, List, Dict, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from core.config import settings
import structlog

logger = structlog.get_logger()


class Neo4jGraphBuilder:

    def __init__(self):
        self._driver: Optional[AsyncDriver] = None

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=50,
            )
        return self._driver

    # ── Schema Init ───────────────────────────────────────────────────────────

    async def init_schema(self):
        """Create constraints and indexes on first startup."""
        driver = await self._get_driver()
        stmts = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Meeting)  REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User)     REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Task)     REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Risk)     REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tp:Topic)   REQUIRE tp.name IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (d:Decision) ON (d.org_id)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Task)     ON (t.org_id)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Meeting)  ON (m.org_id)",
        ]
        try:
            async with driver.session() as session:
                for stmt in stmts:
                    await session.run(stmt)
            logger.info("Neo4j schema initialized")
        except Exception as e:
            logger.error("Neo4j schema init failed", error=str(e))

    # ── Meeting ───────────────────────────────────────────────────────────────

    async def upsert_meeting(self, meeting_id: str, org_id: str, title: str):
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (m:Meeting {id: $id})
                SET m.org_id    = $org_id,
                    m.title     = $title,
                    m.updated_at = datetime()
                """,
                id=meeting_id, org_id=org_id, title=title,
            )

    # ── Decision ──────────────────────────────────────────────────────────────

    async def add_decision(
        self,
        decision_id: str,
        meeting_id: str,
        org_id: str,
        description: str,
        made_by: Optional[str] = None,
        revises_id: Optional[str] = None,
    ):
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (d:Decision {id: $id})
                SET d.org_id      = $org_id,
                    d.description = $description,
                    d.created_at  = datetime()
                WITH d
                MATCH (m:Meeting {id: $meeting_id})
                MERGE (d)-[:DISCUSSED_IN]->(m)
                """,
                id=decision_id, org_id=org_id,
                description=description, meeting_id=meeting_id,
            )
            if made_by:
                await session.run(
                    """
                    MATCH (d:Decision {id: $decision_id})
                    MERGE (u:User {name: $name})
                    MERGE (d)-[:MADE_BY]->(u)
                    """,
                    decision_id=decision_id, name=made_by,
                )
            if revises_id:
                await session.run(
                    """
                    MATCH (d:Decision {id: $new_id})
                    MATCH (old:Decision {id: $old_id})
                    MERGE (d)-[:REVISES]->(old)
                    """,
                    new_id=decision_id, old_id=revises_id,
                )

    # ── Task ──────────────────────────────────────────────────────────────────

    async def add_task(
        self,
        task_id: str,
        meeting_id: str,
        org_id: str,
        description: str,
        assignee: Optional[str] = None,
        deadline: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        is_vague: bool = False,
    ):
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (t:Task {id: $id})
                SET t.org_id      = $org_id,
                    t.description = $description,
                    t.deadline    = $deadline,
                    t.is_vague    = $is_vague,
                    t.created_at  = datetime()
                WITH t
                MATCH (m:Meeting {id: $meeting_id})
                MERGE (t)-[:DISCUSSED_IN]->(m)
                """,
                id=task_id, org_id=org_id, description=description,
                deadline=deadline, is_vague=is_vague, meeting_id=meeting_id,
            )
            if assignee:
                await session.run(
                    """
                    MATCH (t:Task {id: $task_id})
                    MERGE (u:User {name: $assignee})
                    MERGE (t)-[:ASSIGNED_TO]->(u)
                    """,
                    task_id=task_id, assignee=assignee,
                )
            if dependencies:
                for dep_id in dependencies:
                    await session.run(
                        """
                        MATCH (t:Task {id: $task_id})
                        MATCH (dep:Task {id: $dep_id})
                        MERGE (t)-[:DEPENDS_ON]->(dep)
                        """,
                        task_id=task_id, dep_id=dep_id,
                    )

    # ── Risk ──────────────────────────────────────────────────────────────────

    async def add_risk(
        self,
        risk_id: str,
        meeting_id: str,
        org_id: str,
        description: str,
        is_blocker: bool = False,
        blocks_task_id: Optional[str] = None,
    ):
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (r:Risk {id: $id})
                SET r.org_id      = $org_id,
                    r.description = $description,
                    r.is_blocker  = $is_blocker,
                    r.created_at  = datetime()
                WITH r
                MATCH (m:Meeting {id: $meeting_id})
                MERGE (r)-[:DISCUSSED_IN]->(m)
                """,
                id=risk_id, org_id=org_id, description=description,
                is_blocker=is_blocker, meeting_id=meeting_id,
            )
            if is_blocker and blocks_task_id:
                await session.run(
                    """
                    MATCH (r:Risk {id: $risk_id})
                    MATCH (t:Task {id: $task_id})
                    MERGE (r)-[:BLOCKS]->(t)
                    """,
                    risk_id=risk_id, task_id=blocks_task_id,
                )

    # ── Topics ────────────────────────────────────────────────────────────────

    async def add_topics(self, meeting_id: str, topics: List[str]):
        driver = await self._get_driver()
        async with driver.session() as session:
            for topic in topics:
                await session.run(
                    """
                    MERGE (tp:Topic {name: $name})
                    WITH tp
                    MATCH (m:Meeting {id: $meeting_id})
                    MERGE (m)-[:TAGGED_WITH]->(tp)
                    """,
                    name=topic.lower().strip(), meeting_id=meeting_id,
                )

    # ── Graph Queries ─────────────────────────────────────────────────────────

    async def get_decision_evolution(
        self, topic_keyword: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Trace how decisions about a topic evolved across meetings."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (d:Decision)
                WHERE d.org_id = $org_id
                  AND toLower(d.description) CONTAINS toLower($keyword)
                OPTIONAL MATCH (d)-[:REVISES*]->(old:Decision)
                OPTIONAL MATCH (d)-[:DISCUSSED_IN]->(m:Meeting)
                RETURN d.id          AS id,
                       d.description AS description,
                       m.title       AS meeting,
                       collect(old.description) AS revision_chain
                ORDER BY d.created_at ASC
                """,
                org_id=org_id, keyword=topic_keyword,
            )
            return [dict(r) async for r in result]

    async def get_task_dependencies(self, org_id: str) -> List[Dict[str, Any]]:
        """All DEPENDS_ON edges — useful for rendering a dependency DAG."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task)-[:DEPENDS_ON]->(dep:Task)
                WHERE t.org_id = $org_id
                RETURN t.id          AS task_id,
                       t.description AS task,
                       dep.id        AS dep_id,
                       dep.description AS depends_on
                """,
                org_id=org_id,
            )
            return [dict(r) async for r in result]

    async def get_blockers_for_user(
        self, user_name: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Find all active blockers affecting a user's assigned tasks."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {name: $user})<-[:ASSIGNED_TO]-(t:Task)
                WHERE t.org_id = $org_id
                OPTIONAL MATCH (r:Risk)-[:BLOCKS]->(t)
                RETURN t.description    AS task,
                       collect(r.description) AS blockers
                """,
                user=user_name, org_id=org_id,
            )
            return [dict(r) async for r in result]

    async def find_related_decisions(
        self,
        decision_text: str,
        org_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find decisions in meetings that share topics with the queried decision.
        Used by the hybrid search endpoint for graph-based retrieval.
        """
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (d:Decision)-[:DISCUSSED_IN]->(m:Meeting)-[:TAGGED_WITH]->(tp:Topic)
                WHERE d.org_id = $org_id
                  AND toLower(d.description) CONTAINS toLower($keyword)
                MATCH (related:Decision)-[:DISCUSSED_IN]->
                      (m2:Meeting)-[:TAGGED_WITH]->(tp)
                WHERE related.id <> d.id AND related.org_id = $org_id
                RETURN DISTINCT
                       related.id          AS id,
                       related.description AS description,
                       m2.title            AS meeting,
                       count(tp)           AS shared_topics
                ORDER BY shared_topics DESC
                LIMIT $lim
                """,
                org_id=org_id,
                keyword=decision_text[:60],
                lim=limit,
            )
            return [dict(r) async for r in result]

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None


# Module-level singleton
graph_builder = Neo4jGraphBuilder()
