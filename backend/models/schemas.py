from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ── Auth ──────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    org_id: UUID


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    org_id: UUID
    role: str

    class Config:
        from_attributes = True


# ── Meetings ──────────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str
    org_id: UUID


class MeetingOut(BaseModel):
    id: UUID
    title: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Extraction (LLM output validated via Pydantic) ────────────────────────────

class ExtractedTask(BaseModel):
    description: str = Field(..., description="What needs to be done")
    assignee: Optional[str] = Field(None, description="Person responsible")
    deadline_raw: Optional[str] = Field(None, description="Deadline as mentioned in speech")
    is_vague: bool = Field(False, description="True if commitment is vague (maybe/soon/try/etc)")
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class ExtractedDecision(BaseModel):
    description: str = Field(..., description="What was decided")
    made_by: Optional[str] = Field(None, description="Who made the decision")
    rationale: Optional[str] = Field(None, description="Why this was decided")
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class ExtractedRisk(BaseModel):
    description: str = Field(..., description="The risk, blocker or concern")
    severity: str = Field("medium", description="low / medium / high / critical")
    category: str = Field("blocker", description="blocker / dependency / timeline / resource")
    is_blocker: bool = Field(False, description="True if this actively blocks progress")
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    tasks: List[ExtractedTask] = Field(default_factory=list)
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    risks: List[ExtractedRisk] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)


# ── Transcript ────────────────────────────────────────────────────────────────

class TranscriptChunk(BaseModel):
    text: str
    speaker: Optional[str] = None
    start_time: float
    end_time: float
    is_stable: bool = False
    confidence: float = 1.0


# ── Live Events ───────────────────────────────────────────────────────────────

class LiveEvent(BaseModel):
    event_type: str   # transcript | extraction | score
    meeting_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Execution Score ───────────────────────────────────────────────────────────

class ExecutionScoreOut(BaseModel):
    score: float
    tasks_total: int
    tasks_with_owner: int
    tasks_with_deadline: int
    vague_count: int
    blocker_count: int
    computed_at: datetime

    class Config:
        from_attributes = True


# ── Search ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    org_id: UUID
    top_k: int = Field(10, ge=1, le=50)
    use_graph: bool = True
    meeting_id: Optional[UUID] = None


class SearchResult(BaseModel):
    source: str   # vector | graph | sql
    score: float
    content: str
    meeting_id: Optional[str] = None
    meeting_title: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
