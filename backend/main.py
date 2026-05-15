"""
AI Execution Intelligence Platform — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
import structlog

from core.config import settings
from core.database import get_db, init_db
from core.auth import verify_password, create_access_token, hash_password
from models.db_models import User, Organization
from models.schemas import Token, UserCreate, UserOut
from api.routes import meetings, search, analytics, websocket
from services.graph.neo4j_builder import graph_builder

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting AI Execution Intelligence Platform", env=settings.environment)

    # Initialize PostgreSQL tables
    await init_db()
    logger.info("Database tables ready")

    # Initialize Neo4j schema
    await graph_builder.init_schema()
    logger.info("Neo4j schema ready")

    # Ensure MinIO bucket exists
    try:
        from minio import Minio
        import io
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
        )
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
            logger.info("MinIO bucket created", bucket=settings.minio_bucket)
        else:
            logger.info("MinIO bucket exists", bucket=settings.minio_bucket)
    except Exception as e:
        logger.warning("MinIO initialization failed (non-fatal)", error=str(e))

    logger.info("Platform ready — accepting requests")
    yield

    # Shutdown
    await graph_builder.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI Execution Intelligence Platform",
    description="Transforms live meetings into structured execution intelligence.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/token", response_model=Token, tags=["auth"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    """Exchange email + password for a JWT access token."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({
        "sub":    str(user.id),
        "org_id": str(user.org_id),
        "email":  user.email,
    })
    return Token(access_token=token)


@app.post("/auth/register", response_model=UserOut, status_code=201, tags=["auth"])
async def register(payload: UserCreate, db=Depends(get_db)):
    """Register a new user within an existing organization."""
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    import uuid
    user = User(
        id=uuid.uuid4(),
        org_id=payload.org_id,
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.post("/auth/org", status_code=201, tags=["auth"])
async def create_organization(name: str, slug: str, db=Depends(get_db)):
    """Create a new organization (onboarding step)."""
    import uuid
    org = Organization(id=uuid.uuid4(), name=name, slug=slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return {"id": str(org.id), "name": org.name, "slug": org.slug}


# ── API Routers ───────────────────────────────────────────────────────────────

app.include_router(meetings.router)
app.include_router(search.router)
app.include_router(analytics.router)
app.include_router(websocket.router)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.environment,
    }


@app.get("/", tags=["system"])
async def root():
    return {
        "name": "AI Execution Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8128)