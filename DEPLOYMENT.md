# AI Execution Intelligence Platform — Deployment Guide

## Prerequisites

| Tool | Min Version | Notes |
|---|---|---|
| Docker | 24.0+ | |
| docker compose | v2.0+ | |
| NVIDIA Driver | 525+ | Optional but recommended |
| nvidia-container-toolkit | latest | For GPU passthrough |

---

## Step 1 — Clone and Configure

```bash
cd ai-execution-platform
cp .env.example .env
```

Edit `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"

NEO4J_PASSWORD=your_strong_password

HF_TOKEN=hf_xxxxxxxxxxxxx

WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

---

## Step 2 — Start Infrastructure Services

```bash
docker compose pull
docker compose up -d postgres redis neo4j minio
```

Wait ~30 seconds for databases to initialize.

```bash
docker compose ps
```

---

## Step 3 — Start Application Services

```bash
docker compose up -d backend worker ollama nginx flower
```

Check logs:

```bash
docker compose logs -f backend
docker compose logs -f worker
```

---

## Step 4 — Pull LLM Model

The Ollama container needs the model downloaded on first run:

```bash
docker compose exec ollama ollama pull mistral:7b
docker compose exec ollama ollama list
```

Alternative larger models (better extraction quality):
```bash
docker compose exec ollama ollama pull mixtral:8x7b
docker compose exec ollama ollama pull llama3:8b
```

Then update `OLLAMA_MODEL` in `.env` and restart the worker.

---

## Step 5 — Initialize Database Indexes

After the first backend startup creates the tables, apply the FTS and vector indexes:

```bash
docker compose exec postgres psql \
  -U aiexec -d aiexec_db \
  -c "\i /docker-entrypoint-initdb.d/01-init.sql"
```

Or manually via `psql`:

```sql
CREATE INDEX idx_transcripts_fts ON transcripts USING gin(to_tsvector('english', text));
CREATE INDEX idx_tasks_fts ON tasks USING gin(to_tsvector('english', description));
CREATE INDEX idx_transcripts_embedding_hnsw ON transcripts USING hnsw (embedding vector_cosine_ops);
```

---

## Step 6 — Create Your First Organization and User

```bash
# 1. Create an organization
curl -X POST "http://localhost:8000/auth/org?name=My+Company&slug=myco"
# → {"id": "ORG_UUID", "name": "My Company", "slug": "myco"}

# 2. Register a user (replace ORG_UUID)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@aiexec.com",
    "name": "Demo User",
    "password": "demo1234",
    "org_id": "ORG_UUID"
  }'

# 3. Get an access token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=demo@aiexec.com&password=demo1234" | jq -r .access_token)
echo $TOKEN
```

---

## Step 7 — Create a Meeting and Test

```bash
ORG_ID="your-org-uuid-here"

# Create meeting
MEETING=$(curl -s -X POST http://localhost:8000/meetings/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Q3 Planning\", \"org_id\": \"$ORG_ID\"}" | jq -r .id)
echo "Meeting ID: $MEETING"

# Start meeting
curl -X POST "http://localhost:8000/meetings/$MEETING/start" \
  -H "Authorization: Bearer $TOKEN"

# Upload a test audio file
curl -X POST "http://localhost:8000/meetings/$MEETING/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_meeting.wav"
```

---

## Step 8 — Open the Dashboard

| URL | Description |
|---|---|
| `http://localhost` | Live Dashboard UI |
| `http://localhost:8000/docs` | FastAPI Swagger UI |
| `http://localhost:7474` | Neo4j Browser (user: neo4j) |
| `http://localhost:9001` | MinIO Console |
| `http://localhost:5555` | Celery Flower (worker monitoring) |

1. Open `http://localhost`
2. Enter your Meeting ID in the input field
3. Click **Connect**
4. Click **🎤 Start Mic** to stream live audio

---

## CPU-Only Deployment (no GPU)

Edit `.env`:
```bash
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_MODEL_SIZE=base   # or 'small' — large-v3 is too slow on CPU
```

Remove GPU resource blocks from `docker-compose.yml`:
```yaml
# Comment out or remove these sections from 'worker' and 'ollama':
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
```

---

## Scaling for Production

### Horizontal API scaling
```bash
docker compose up -d --scale backend=3
```

### Dedicated GPU worker nodes
```bash
# Run audio_pipeline queue on GPU nodes only
celery -A workers.pipeline_worker worker \
  -Q audio_pipeline \
  --concurrency=1

# Run extraction on separate nodes
celery -A workers.pipeline_worker worker \
  -Q extraction \
  --concurrency=4

# Run graph updates on CPU nodes
celery -A workers.pipeline_worker worker \
  -Q graph_update \
  --concurrency=8
```

### Database connection pooling
Add PgBouncer in front of PostgreSQL:
```yaml
pgbouncer:
  image: edoburu/pgbouncer
  environment:
    DATABASE_URL: postgresql://aiexec:pass@postgres/aiexec_db
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | JWT signing key (required) |
| `DATABASE_URL` | postgresql+asyncpg://... | Async PostgreSQL URL |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection URL |
| `NEO4J_URI` | bolt://neo4j:7687 | Neo4j bolt URI |
| `OLLAMA_MODEL` | mistral:7b | LLM model name |
| `WHISPER_MODEL_SIZE` | large-v3 | Whisper model size |
| `WHISPER_DEVICE` | cuda | cuda or cpu |
| `HF_TOKEN` | — | HuggingFace token for diarization |
| `CHUNK_WINDOW_SEC` | 10 | ASR sliding window size |
| `CHUNK_STRIDE_SEC` | 8 | ASR stride (overlap = W - S) |
| `STABILIZATION_K` | 3 | Windows required for token stability |
