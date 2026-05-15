from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean,
    DateTime, ForeignKey, JSON, Enum as SAEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
import enum
from core.database import Base
from core.config import settings


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    meetings = relationship("Meeting", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    speaker_label = Column(String(50))  # maps diarization label → user
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")

    __table_args__ = (
        Index("idx_users_org_id", "org_id"),
    )


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(SAEnum(MeetingStatus), default=MeetingStatus.SCHEDULED)
    audio_path = Column(String(512))       # MinIO object path
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    participants = Column(JSON, default=list)

    organization = relationship("Organization", back_populates="meetings")
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="meeting", cascade="all, delete-orphan")
    execution_scores = relationship("ExecutionScore", back_populates="meeting", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_meetings_org_id", "org_id"),
        Index("idx_meetings_status", "status"),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    speaker_label = Column(String(50))        # SPEAKER_00 / SPEAKER_01
    speaker_name = Column(String(255))        # resolved human name
    text = Column(Text, nullable=False)
    start_time = Column(Float)               # seconds from meeting start
    end_time = Column(Float)
    confidence = Column(Float, default=1.0)
    is_stable = Column(Boolean, default=False)
    embedding = Column(Vector(settings.embedding_dim))
    chunk_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcripts")

    __table_args__ = (
        Index("idx_transcripts_meeting_id", "meeting_id"),
        Index("idx_transcripts_org_id", "org_id"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    description = Column(Text, nullable=False)
    assignee_name = Column(String(255))
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deadline_raw = Column(String(255))        # "next Friday" as spoken
    deadline_iso = Column(DateTime)           # normalized ISO datetime
    status = Column(SAEnum(TaskStatus), default=TaskStatus.OPEN)
    confidence = Column(Float, default=0.0)
    is_vague = Column(Boolean, default=False)
    dependencies = Column(JSON, default=list) # list of task_ids this depends on
    source_transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=True)
    neo4j_node_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")

    __table_args__ = (
        Index("idx_tasks_meeting_id", "meeting_id"),
        Index("idx_tasks_org_id", "org_id"),
    )


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    description = Column(Text, nullable=False)
    made_by = Column(String(255))
    rationale = Column(Text)
    confidence = Column(Float, default=0.0)
    revises_decision_id = Column(UUID(as_uuid=True), ForeignKey("decisions.id"), nullable=True)
    neo4j_node_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="decisions")

    __table_args__ = (
        Index("idx_decisions_meeting_id", "meeting_id"),
        Index("idx_decisions_org_id", "org_id"),
    )


class Risk(Base):
    __tablename__ = "risks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="medium")   # low / medium / high / critical
    category = Column(String(50), default="blocker")  # blocker / dependency / timeline / resource
    is_blocker = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="risks")

    __table_args__ = (
        Index("idx_risks_meeting_id", "meeting_id"),
    )


class ExecutionScore(Base):
    __tablename__ = "execution_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    score = Column(Float, default=0.0)              # clamped 0.0 – 1.0
    tasks_total = Column(Integer, default=0)
    tasks_with_owner = Column(Integer, default=0)
    tasks_with_deadline = Column(Integer, default=0)
    vague_count = Column(Integer, default=0)
    blocker_count = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="execution_scores")

    __table_args__ = (
        Index("idx_exec_scores_org_id", "org_id"),
        Index("idx_exec_scores_meeting_id", "meeting_id"),
    )
