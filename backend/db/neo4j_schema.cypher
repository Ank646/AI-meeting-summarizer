// ============================================================
// AI Execution Intelligence Platform — Neo4j Graph Schema
// Run these statements on first Neo4j startup (or via init hook)
// ============================================================

// ── Uniqueness Constraints ───────────────────────────────────
CREATE CONSTRAINT IF NOT EXISTS FOR (m:Meeting)  REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (u:User)     REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (t:Task)     REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (r:Risk)     REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (tp:Topic)   REQUIRE tp.name IS UNIQUE;

// ── Property Indexes ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS FOR (d:Decision) ON (d.org_id);
CREATE INDEX IF NOT EXISTS FOR (t:Task)     ON (t.org_id);
CREATE INDEX IF NOT EXISTS FOR (m:Meeting)  ON (m.org_id);
CREATE INDEX IF NOT EXISTS FOR (u:User)     ON (u.name);

// ── Example Queries ───────────────────────────────────────────

// 1. All decisions made in a meeting
// MATCH (d:Decision)-[:DISCUSSED_IN]->(m:Meeting {id: $meeting_id})
// RETURN d.description, d.made_by ORDER BY d.created_at

// 2. Decision revision chain (how a decision evolved over time)
// MATCH (d:Decision)-[:REVISES*1..5]->(old:Decision)
// RETURN d.description AS current, collect(old.description) AS history

// 3. All blockers affecting a specific user
// MATCH (u:User {name: "Alice"})<-[:ASSIGNED_TO]-(t:Task)<-[:BLOCKS]-(r:Risk)
// RETURN t.description AS task, r.description AS blocked_by

// 4. Cross-meeting topic graph (which meetings share topics)
// MATCH (m1:Meeting)-[:TAGGED_WITH]->(tp:Topic)<-[:TAGGED_WITH]-(m2:Meeting)
// WHERE m1.id <> m2.id AND m1.org_id = $org_id
// RETURN m1.title, tp.name, m2.title, count(*) AS weight
// ORDER BY weight DESC

// 5. Task dependency path (critical path analysis)
// MATCH path = (t:Task)-[:DEPENDS_ON*1..6]->(dep:Task)
// WHERE t.org_id = $org_id AND NOT ()-[:DEPENDS_ON]->(t)
// RETURN path, length(path) AS depth
// ORDER BY depth DESC

// 6. Owner workload (all tasks assigned to each person)
// MATCH (u:User)<-[:ASSIGNED_TO]-(t:Task)
// WHERE t.org_id = $org_id
// RETURN u.name, count(t) AS task_count, collect(t.description) AS tasks
// ORDER BY task_count DESC

// 7. Decisions that were later revised (unstable decisions)
// MATCH (new:Decision)-[:REVISES]->(old:Decision)
// RETURN old.description AS original, new.description AS revised,
//        old.created_at, new.created_at

// 8. Meeting with most blockers
// MATCH (r:Risk {is_blocker: true})-[:DISCUSSED_IN]->(m:Meeting)
// WHERE m.org_id = $org_id
// RETURN m.title, count(r) AS blocker_count
// ORDER BY blocker_count DESC
// LIMIT 10
