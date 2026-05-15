from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "AI Execution Intelligence Platform"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aiexec_db"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "aiexec_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_secret"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin_secret"
    minio_bucket: str = "meetings"
    minio_secure: bool = False

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b"

    # Whisper
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # HuggingFace (required for pyannote diarization)
    hf_token: Optional[str] = None

    # Embeddings
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dim: int = 1024

    # Pipeline parameters
    chunk_window_sec: int = 10
    chunk_stride_sec: int = 8
    stabilization_k: int = 3

    class Config:
        env_file = "../.env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
