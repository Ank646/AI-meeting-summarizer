-- ============================================================
-- AI Execution Intelligence Platform — PostgreSQL Init Script
-- Runs automatically on first postgres container startup.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Full-text search indexes
-- (Tables are created by SQLAlchemy on first app startup)
-- Run this script AFTER the first app startup if needed.
-- ============================================================

-- Transcript full-text search
CREATE INDEX IF NOT EXISTS idx_transcripts_fts
    ON transcripts USING gin(to_tsvector('english', text));

-- Task full-text search
CREATE INDEX IF NOT EXISTS idx_tasks_fts
    ON tasks USING gin(to_tsvector('english', description));

-- Decision full-text search
CREATE INDEX IF NOT EXISTS idx_decisions_fts
    ON decisions USING gin(to_tsvector('english', description));

-- Risk full-text search
CREATE INDEX IF NOT EXISTS idx_risks_fts
    ON risks USING gin(to_tsvector('english', description));

-- ============================================================
-- Vector similarity index (HNSW for fast ANN search)
-- m=16: number of neighbors per layer
-- ef_construction=64: build-time accuracy/speed tradeoff
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_transcripts_embedding_hnsw
    ON transcripts USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================
-- Row-Level Security (multi-tenant isolation)
-- The backend sets: SET LOCAL app.current_org_id = '...'
-- before executing queries in RLS-enabled tables.
-- ============================================================

ALTER TABLE meetings    ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks       ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE risks       ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_scores ENABLE ROW LEVEL SECURITY;

-- Allow service role to bypass RLS (set this on your app db user)
-- ALTER ROLE aiexec BYPASSRLS;

-- Org isolation policies
CREATE POLICY IF NOT EXISTS org_policy_meetings ON meetings
    USING (org_id::text = current_setting('app.current_org_id', true));

CREATE POLICY IF NOT EXISTS org_policy_tasks ON tasks
    USING (org_id::text = current_setting('app.current_org_id', true));

CREATE POLICY IF NOT EXISTS org_policy_decisions ON decisions
    USING (org_id::text = current_setting('app.current_org_id', true));

CREATE POLICY IF NOT EXISTS org_policy_transcripts ON transcripts
    USING (org_id::text = current_setting('app.current_org_id', true));

CREATE POLICY IF NOT EXISTS org_policy_risks ON risks
    USING (org_id::text = current_setting('app.current_org_id', true));

CREATE POLICY IF NOT EXISTS org_policy_exec_scores ON execution_scores
    USING (org_id::text = current_setting('app.current_org_id', true));
