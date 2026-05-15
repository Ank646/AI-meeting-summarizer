# AI Meeting Summarizer

Real-time meeting intelligence platform — transcribes audio, diarizes speakers, extracts decisions/tasks/risks, builds a knowledge graph, and surfaces actionable summaries through a live dashboard.

## Architecture

```
Browser (Next.js)
     │  WebSocket + REST
     ▼
FastAPI Gateway (port 8000)
     │  Redis Streams
     ├──▶ ASR Worker       — Whisper large-v3 (GPU)
     ├──▶ Diarization Worker — pyannote.audio
     ├──▶ Extraction Worker — LangChain + Ollama LLM
     └──▶ Graph Worker     — Neo4j knowledge graph

Storage:  PostgreSQL + pgvector · Neo4j · MinIO · Redis
Proxy:    Nginx (port 80)
```

## Services

| Service | Port | Description |
|---|---|---|
| FastAPI backend | 8000 | REST API + WebSocket gateway |
| Next.js frontend | 80 | Live dashboard via Nginx |
| PostgreSQL + pgvector | 5432 | Transcripts, embeddings, metadata |
| Redis | 6379 | Celery broker, pub/sub, streams |
| Neo4j | 7474 / 7687 | Knowledge graph |
| MinIO | 9000 / 9001 | Audio file storage |
| Ollama | 11434 | Local LLM server |
| Flower | 5555 | Celery worker monitoring |

## Quick Start

### Prerequisites

- Docker 24.0+, docker compose v2
- NVIDIA driver 525+ with `nvidia-container-toolkit` (recommended for GPU)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

NEO4J_PASSWORD=your_strong_password
HF_TOKEN=hf_xxxxxxxxxxxxx        # Hugging Face token for pyannote models
WHISPER_MODEL_SIZE=large-v3
```

### 2. Start infrastructure

```bash
docker compose up -d postgres redis neo4j minio
```

Wait ~30 seconds for databases to initialise, then verify:

```bash
docker compose ps
```

### 3. Start the full stack

```bash
docker compose up -d
```

### 4. Pull an LLM model (first run)

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

### 5. Open the dashboard

Navigate to [http://localhost](http://localhost)

## Project Structure

```
.
├── backend/
│   ├── api/            # FastAPI routes (meetings, search, analytics, websocket)
│   ├── core/           # Config, DB session, Redis client, auth
│   ├── db/             # SQL init schema + Neo4j Cypher schema
│   ├── models/         # SQLAlchemy ORM models + Pydantic schemas
│   ├── services/
│   │   ├── asr/        # Whisper transcription + stabilizer
│   │   ├── audio/      # Preprocessing, VAD
│   │   ├── diarization/# pyannote speaker diarization
│   │   ├── embeddings/ # Sentence-transformer embeddings
│   │   ├── extraction/ # LLM-based decision/task/risk extraction
│   │   ├── graph/      # Neo4j knowledge graph builder
│   │   ├── pipeline/   # Two-pass summarisation pipeline
│   │   └── topics/     # Topic segmentation
│   ├── workers/        # Celery workers (ASR, diarization, pipeline)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend-next/
│   ├── app/            # Next.js App Router pages
│   ├── components/     # Dashboard, Layout, UI components
│   ├── hooks/          # WebSocket, microphone, mock simulator
│   ├── lib/            # API client, types, mock data
│   └── store/          # Zustand state stores
├── infra/
│   └── nginx/nginx.conf
├── docker-compose.yml
├── .env.example
└── DEPLOYMENT.md       # Detailed deployment and troubleshooting guide
```

## Key Features

- **Real-time transcription** — Whisper large-v3 via faster-whisper, streamed over WebSocket
- **Speaker diarization** — pyannote.audio identifies who said what
- **LLM extraction** — Ollama (llama3.1) extracts decisions, action items, risks, and topics
- **Two-pass pipeline** — live pass for speed, second pass for accuracy after meeting ends
- **Knowledge graph** — Neo4j links speakers, topics, decisions, and action items across meetings
- **Semantic search** — pgvector cosine similarity over transcript embeddings
- **Execution scoring** — heuristic + LLM-based meeting effectiveness score

## Tech Stack

**Backend:** FastAPI · Celery · SQLAlchemy · LangChain · faster-whisper · pyannote.audio · sentence-transformers

**Frontend:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · Zustand

**Infrastructure:** PostgreSQL + pgvector · Redis · Neo4j · MinIO · Ollama · Nginx · Docker

## Environment Variables

See [.env.example](.env.example) for the full list. Key variables:

| Variable | Description |
|---|---|
| `HF_TOKEN` | Hugging Face token (required for pyannote models) |
| `WHISPER_MODEL_SIZE` | Model size: `tiny`, `base`, `large-v3` (default) |
| `WHISPER_DEVICE` | `cuda` or `cpu` |
| `NEO4J_PASSWORD` | Neo4j database password |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://ollama:11434`) |
| `OLLAMA_MODEL` | LLM model name (default: `llama3.1:8b`) |

## Scaling Workers

```bash
# Scale ASR workers (GPU-bound)
docker compose up --scale asr-worker=2 -d

# Scale extraction workers (LLM-bound)
docker compose up --scale extraction-worker=4 -d
```

Monitor workers at [http://localhost:5555](http://localhost:5555) (Flower).

## License

MIT
