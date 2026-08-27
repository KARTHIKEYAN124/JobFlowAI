import enum
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings


def uid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class ApplicationStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    SAVED = "SAVED"
    PREPARING = "PREPARING"
    READY = "READY"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    high_match_email: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_digest: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    interview_preparation: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_email: Mapped[str] = mapped_column(String(320), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    headline: Mapped[str] = mapped_column(String(240), default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[list] = mapped_column(JSON, default=list)
    projects: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[dict] = mapped_column(JSON, default=dict)
    preferred_roles: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    expected_salary: Mapped[str] = mapped_column(String(80), default="")
    remote_preference: Mapped[str] = mapped_column(String(40), default="hybrid")
    searchable_text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    extracted_text: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResumeFile(Base):
    __tablename__ = "resume_files"
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int] = mapped_column(Integer)
    stored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    website: Mapped[str] = mapped_column(String(500), default="")


class JobSource(Base):
    __tablename__ = "job_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    source_type: Mapped[str] = mapped_column(String(40))
    endpoint: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    external_id: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(240), index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(80), default="Germany")
    remote_type: Mapped[str] = mapped_column(String(40), default="hybrid")
    employment_type: Mapped[str] = mapped_column(String(80), default="working_student")
    category: Mapped[str] = mapped_column(String(40), default="SOFTWARE")
    posted_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(120))
    application_url: Mapped[str] = mapped_column(String(1000))
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    language_requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    overall_score: Mapped[float] = mapped_column(Float)
    technical_score: Mapped[float] = mapped_column(Float)
    semantic_score: Mapped[float] = mapped_column(Float)
    role_score: Mapped[float] = mapped_column(Float)
    location_score: Mapped[float] = mapped_column(Float)
    experience_score: Mapped[float] = mapped_column(Float)
    education_score: Mapped[float] = mapped_column(Float)
    language_score: Mapped[float] = mapped_column(Float)
    freshness_score: Mapped[float] = mapped_column(Float)
    employment_score: Mapped[float] = mapped_column(Float)
    matched_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.SAVED
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    followup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    followup_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationDocument(Base):
    __tablename__ = "application_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PortalSession(Base):
    __tablename__ = "portal_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    __table_args__ = (UniqueConstraint("user_id", "field_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(160))
    question: Mapped[str] = mapped_column(String(500), default="")
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow: Mapped[str] = mapped_column(String(160), index=True)
    execution_id: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40))
    error: Mapped[str] = mapped_column(Text, default="")
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowDeadLetter(Base):
    __tablename__ = "workflow_dead_letters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow: Mapped[str] = mapped_column(String(160), index=True)
    execution_id: Mapped[str] = mapped_column(String(160), default="")
    error: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(40), default="warning")
    attempts: Mapped[int] = mapped_column(Integer, default=3)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(160))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SkillStatistic(Base):
    __tablename__ = "skill_statistics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    skill: Mapped[str] = mapped_column(String(120), unique=True)
    demand_count: Mapped[int] = mapped_column(default=0)
    gap_count: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_demo_jobs():
    async with SessionLocal() as session:
        if await session.scalar(select(func.count()).select_from(Job)):
            return
        now = datetime.utcnow()
        demos = [
            (
                "1",
                "Backend Working Student",
                "Vega Mobility",
                "Berlin",
                "hybrid",
                "BACKEND",
                ["Java", "Spring Boot", "Docker", "AWS"],
                ["Kafka"],
            ),
            (
                "2",
                "Werkstudent AI Engineering",
                "Northstar Labs",
                "Potsdam",
                "remote",
                "AI",
                ["Python", "FastAPI", "RAG", "Docker"],
                ["Kubernetes"],
            ),
            (
                "3",
                "Junior Cloud Developer",
                "Fjord Systems",
                "Berlin",
                "hybrid",
                "CLOUD",
                ["AWS", "Python", "PostgreSQL"],
                ["Terraform"],
            ),
            (
                "4",
                "Working Student Full Stack",
                "Orbit Commerce",
                "Germany",
                "remote",
                "FULLSTACK",
                ["React", "TypeScript", "FastAPI"],
                ["Next.js"],
            ),
        ]
        for index, (job_id, title, company, location, remote, category, required, preferred) in enumerate(
            demos
        ):
            session.add(
                Job(
                    id=job_id,
                    external_id=f"demo-{job_id}",
                    company_name=company,
                    title=title,
                    description=f"Join {company} to build reliable products. Work with {', '.join(required)} and develop practical engineering experience.",
                    location=location,
                    remote_type=remote,
                    employment_type="working_student",
                    category=category,
                    posted_at=now - timedelta(hours=index * 8),
                    source="JobFlow demo",
                    application_url=f"https://example.com/jobs/{job_id}",
                    required_skills=required,
                    preferred_skills=preferred,
                    language_requirements={"English": "B2"},
                    embedding=[],
                )
            )
        await session.commit()
