import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from io import BytesIO
from time import monotonic
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from pypdf import PdfReader
from sqlalchemy import Text, and_, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import (
    AIUsage,
    Application,
    ApplicationDocument,
    ApplicationStatus,
    CandidateAnswer,
    Job,
    JobMatch,
    PortalSession,
    Profile,
    Resume,
    ResumeFile,
    User,
    UserPreference,
    WorkflowDeadLetter,
    WorkflowRun,
    get_db,
)
from app.security import (
    create_token,
    current_user,
    hash_password,
    require_role,
    verify_password,
    verify_webhook,
)
from app.services.ai import AIResult, generate_json
from app.services.documents import application_pack, interview_pack, tailored_resume_pdf
from app.services.embeddings import embed_text
from app.services.internet import (
    discover_jobs,
    fetch_application_questions,
    fetch_portal_job,
    sourced_interview_questions,
)
from app.services.jobs import classify, searchable
from app.services.matching import classification, score_match
from app.services.metrics import jobs_ingested, matches_computed, matching_latency, workflow_executions
from app.services.resumes import KNOWN_SKILLS, extract_resume
from app.services.vector_store import search as vector_search
from app.services.vector_store import upsert as vector_upsert

router = APIRouter(prefix="/api/v1")
ATS_SOURCES = [
    "Greenhouse public Job Board API",
    "Lever public Postings API",
    "Ashby public Job Board API",
    "SmartRecruiters public Posting API",
]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)


class Login(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileData(BaseModel):
    full_name: str = ""
    headline: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    languages: dict[str, str] = Field(default_factory=dict)
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    expected_salary: str = ""
    remote_preference: str = "hybrid"


class ProfileOut(ProfileData, ORM):
    id: str
    processed_at: datetime | None


class JobIn(BaseModel):
    external_id: str
    title: str = Field(min_length=2, max_length=240)
    company: str = Field(min_length=1, max_length=200)
    location: str
    country: str = "Germany"
    description: str = Field(min_length=20)
    employment_type: str = "working_student"
    remote_type: str = "hybrid"
    posted_at: datetime
    application_url: HttpUrl
    source: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    language_requirements: dict[str, str] = Field(default_factory=dict)


class JobURL(BaseModel):
    url: HttpUrl


class JobOut(ORM):
    id: str
    external_id: str
    title: str
    company_name: str
    location: str
    country: str
    description: str
    remote_type: str
    employment_type: str
    category: str
    posted_at: datetime
    source: str
    application_url: str
    required_skills: list
    preferred_skills: list
    language_requirements: dict


class MatchOut(ORM):
    id: str
    job_id: str
    overall_score: float
    technical_score: float
    semantic_score: float
    matched_skills: list
    missing_skills: list
    explanation: str
    classification: str = ""


class AppCreate(BaseModel):
    job_id: str
    notes: str = ""


class SavedAnswers(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    questions: dict[str, str] = Field(default_factory=dict)


class AppPatch(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    approved: bool | None = None


class AppOut(ORM):
    id: str
    job_id: str
    status: ApplicationStatus
    applied_at: datetime | None
    interview_at: datetime | None
    followup_at: datetime | None
    notes: str
    approved_at: datetime | None
    created_at: datetime


class AIRequest(BaseModel):
    application_id: str | None = None
    job_id: str | None = None
    question: str | None = None


class ResumeRevisionRequest(BaseModel):
    instructions: str = Field(min_length=3, max_length=1000)


class Event(BaseModel):
    workflow: str
    execution_id: str = ""
    status: str = "success"
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class PreferenceData(BaseModel):
    high_match_email: bool = True
    daily_digest: bool = True
    followup_reminders: bool = True
    interview_preparation: bool = True
    notification_email: EmailStr | None = None
    telegram_chat_id: str = Field("", max_length=120)


def portal_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def ai_usage(user_id: str | None, operation: str, result: AIResult) -> AIUsage:
    return AIUsage(
        user_id=user_id,
        operation=operation,
        provider=result.provider,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )


def calculate_match(profile: Profile, target: Job) -> dict:
    started = monotonic()
    values = score_match(profile, target)
    matching_latency.observe(monotonic() - started)
    matches_computed.inc()
    return values


def available_job_clause():
    return and_(
        Job.source != "JobFlow demo",
        or_(Job.source.in_(ATS_SOURCES), Job.posted_at >= datetime.utcnow() - timedelta(days=45)),
    )


def is_demo_job(target: Job) -> bool:
    if target.source == "Greenhouse public Job Board API" and target.external_id.startswith("greenhouse:"):
        return False
    hostname = (urlparse(target.application_url).hostname or "").lower()
    return (
        target.source == "JobFlow demo"
        or hostname in {"example.com", "www.example.com"}
        or hostname.endswith(".example.com")
    )


def application_url(target: Job) -> str:
    if target.source == "Greenhouse public Job Board API" and target.external_id.startswith("greenhouse:"):
        _, board, job_id = target.external_id.split(":", 2)
        return f"https://job-boards.greenhouse.io/{board}/jobs/{job_id}"
    return target.application_url


async def valid_portal_session(token: str, db: AsyncSession) -> PortalSession:
    record = await db.scalar(
        select(PortalSession).where(PortalSession.token_hash == portal_token_hash(token))
    )
    if not record:
        raise HTTPException(404, "Portal session not found")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(410, "Portal session expired")
    record.last_used_at = datetime.utcnow()
    return record


async def scan_public_jobs(profile: Profile, db: AsyncSession) -> dict:
    discovered = await discover_jobs(profile.skills, profile.preferred_roles)
    imported = 0
    matched = 0
    for item in discovered:
        external_id = str(item["slug"])
        source = item.get("source") or "Public job feed"
        target = await db.scalar(select(Job).where(Job.source == source, Job.external_id == external_id))
        if not target:
            description = item["description_text"]
            required = [skill for skill in KNOWN_SKILLS if skill.lower() in description.lower()]
            category, _ = classify(item.get("title", ""), description)
            created_at = item.get("created_at") or 0
            posted_at = (
                datetime.fromtimestamp(created_at, UTC).replace(tzinfo=None)
                if created_at
                else datetime.now(UTC).replace(tzinfo=None)
            )
            job_embedding, _ = await embed_text(description)
            target = Job(
                external_id=external_id,
                company_name=item.get("company_name") or "Unknown company",
                title=item.get("title") or "Untitled role",
                description=description,
                location=item.get("location") or ("Remote" if item.get("remote") else "Germany"),
                remote_type="remote" if item.get("remote") else "onsite",
                employment_type=(item.get("job_types") or ["unspecified"])[0],
                category=category,
                posted_at=posted_at,
                source=source,
                application_url=item.get("url") or "https://www.arbeitnow.com/",
                required_skills=required,
                preferred_skills=item.get("tags") or [],
                language_requirements={},
                embedding=job_embedding,
            )
            db.add(target)
            await db.flush()
            imported += 1
            await vector_upsert(
                "job", target.id, job_embedding, {"title": target.title, "source": target.source}
            )
        values = calculate_match(profile, target)
        match_result = await db.scalar(
            select(JobMatch).where(JobMatch.user_id == profile.user_id, JobMatch.job_id == target.id)
        )
        if match_result:
            for key, value in values.items():
                setattr(match_result, key, value)
        else:
            db.add(JobMatch(user_id=profile.user_id, job_id=target.id, **values))
        matched += 1
    await db.commit()
    sources = sorted({item.get("source") or "Public job feed" for item in discovered})
    return {
        "source": ", ".join(sources) or "public job feeds",
        "sources": sources,
        "found": len(discovered),
        "imported": imported,
        "matched": matched,
        "skills_used": profile.skills,
    }


@router.post("/auth/register", response_model=Token, status_code=201)
async def register(data: Register, db: AsyncSession = Depends(get_db)):
    user = User(email=data.email.lower(), password_hash=hash_password(data.password))
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email already registered") from None
    db.add(Profile(user_id=user.id, full_name=data.full_name))
    await db.commit()
    return Token(access_token=create_token(user))


@router.post("/auth/login", response_model=Token)
async def login(data: Login, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return Token(access_token=create_token(user))


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not result:
        raise HTTPException(404, "Profile not found")
    return result


@router.put("/profile", response_model=ProfileOut)
async def put_profile(
    data: ProfileData, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id)) or Profile(user_id=user.id)
    db.add(profile)
    values = data.model_dump()
    for key, value in values.items():
        setattr(profile, key, value)
    profile.searchable_text = searchable(values)
    profile.embedding, _ = await embed_text(profile.searchable_text)
    profile.processed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(profile)
    await vector_upsert("profile", profile.id, profile.embedding, {"user_id": user.id})
    return profile


@router.post("/resume", status_code=201)
async def post_resume(
    file: UploadFile = File(...), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if file.content_type != "application/pdf" or not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF resumes are accepted")
    content = await file.read(settings.max_resume_bytes + 1)
    if len(content) > settings.max_resume_bytes:
        raise HTTPException(413, "Resume exceeds 5 MB")
    try:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    except Exception:
        raise HTTPException(422, "Unreadable PDF") from None
    if not text.strip():
        raise HTTPException(422, "PDF contains no extractable text")
    structured = extract_resume(text)
    extracted = await generate_json(
        "resume_extraction",
        "Extract resume facts. Never infer or invent facts.",
        f"Resume text:\n{text[:24000]}\n\nReturn keys name, email, education, experience, skills, projects, languages.",
    )
    if extracted:
        ai_data, usage = extracted
        db.add(ai_usage(user.id, "resume_extraction", usage))
        claimed_skills = ai_data.get("skills", []) if isinstance(ai_data.get("skills"), list) else []
        verified_skills = [str(skill) for skill in claimed_skills if str(skill).lower() in text.lower()]
        structured = {
            **structured,
            **{
                key: ai_data[key]
                for key in ("name", "email", "education", "experience", "projects", "languages")
                if key in ai_data
            },
            "skills": list(dict.fromkeys([*structured["skills"], *verified_skills])),
        }
    resume = Resume(
        user_id=user.id,
        filename=file.filename or "resume.pdf",
        content_type=file.content_type,
        extracted_text=text,
        structured_data=structured,
    )
    db.add(resume)
    await db.flush()
    db.add(ResumeFile(resume_id=resume.id, data=content, size=len(content)))
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile:
        profile.skills = list(dict.fromkeys([*profile.skills, *structured["skills"]]))
        profile.searchable_text = " ".join(
            [
                profile.full_name,
                profile.headline,
                *profile.skills,
                *profile.preferred_roles,
                *profile.preferred_locations,
            ]
        )
        profile.embedding, _ = await embed_text(profile.searchable_text)
        profile.processed_at = datetime.utcnow()
    await db.commit()
    if profile:
        await vector_upsert("profile", profile.id, profile.embedding, {"user_id": user.id})
    try:
        job_scan = (
            await scan_public_jobs(profile, db)
            if profile
            else {"found": 0, "imported": 0, "matched": 0, "skills_used": []}
        )
    except Exception as error:
        job_scan = {
            "found": 0,
            "imported": 0,
            "matched": 0,
            "skills_used": structured["skills"],
            "error": f"Public job scan unavailable: {type(error).__name__}",
        }
    return {
        "id": resume.id,
        "filename": resume.filename,
        "characters": len(text),
        "structured_data": structured,
        "created_at": resume.created_at,
        "stored": True,
        "file_size": len(content),
        "download_url": "/api/v1/resume/file",
        "job_scan": job_scan,
    }


@router.get("/resume")
async def get_resume(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    resume = await db.scalar(
        select(Resume).where(Resume.user_id == user.id).order_by(desc(Resume.created_at))
    )
    if not resume:
        raise HTTPException(404, "Resume not found")
    stored = await db.get(ResumeFile, resume.id)
    return {
        "id": resume.id,
        "filename": resume.filename,
        "structured_data": resume.structured_data,
        "created_at": resume.created_at,
        "stored": stored is not None,
        "file_size": stored.size if stored else None,
        "download_url": "/api/v1/resume/file" if stored else None,
    }


@router.get("/resume/file")
async def get_resume_file(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(Resume, ResumeFile)
            .join(ResumeFile, ResumeFile.resume_id == Resume.id)
            .where(Resume.user_id == user.id)
            .order_by(desc(Resume.created_at))
            .limit(1)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Stored resume PDF not found")
    resume, stored = row
    return Response(
        content=stored.data,
        media_type=resume.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(resume.filename)}",
            "Content-Length": str(stored.size),
        },
    )


@router.get("/jobs", response_model=list[JobOut])
async def jobs(
    q: str = "",
    location: str = "",
    category: str = "",
    remote: str = "",
    language: str = "",
    posted_within_days: int = Query(0, ge=0, le=365),
    minimum_match: float = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=100),
    include_demo: bool = False,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Job).order_by(desc(Job.posted_at)).limit(limit)
    if not include_demo:
        statement = statement.where(available_job_clause())
    if q:
        statement = statement.where(or_(Job.title.ilike(f"%{q}%"), Job.company_name.ilike(f"%{q}%")))
    if location:
        statement = statement.where(Job.location.ilike(f"%{location}%"))
    if category:
        statement = statement.where(Job.category == category.upper())
    if remote:
        statement = statement.where(Job.remote_type == remote)
    if posted_within_days:
        statement = statement.where(Job.posted_at >= datetime.utcnow() - timedelta(days=posted_within_days))
    if language:
        statement = statement.where(Job.language_requirements.cast(Text).ilike(f"%{language}%"))
    if minimum_match:
        statement = statement.join(JobMatch).where(
            JobMatch.user_id == user.id, JobMatch.overall_score >= minimum_match
        )
    return list((await db.scalars(statement)).all())


@router.get("/jobs/semantic-search")
async def semantic_jobs(
    q: str = Query(min_length=2, max_length=300),
    limit: int = Query(20, ge=1, le=50),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    query_vector, provider = await embed_text(q)
    indexed = await vector_search(query_vector, "job", limit)
    indexed_ids = [str(item["id"]) for item in indexed]
    if indexed_ids:
        records = {
            job.id: job
            for job in (
                await db.scalars(select(Job).where(Job.id.in_(indexed_ids), available_job_clause()))
            ).all()
        }
        return {
            "provider": "qdrant",
            "jobs": [
                {
                    "job": JobOut.model_validate(records[item["id"]]),
                    "semantic_score": round(float(item["score"]) * 100, 1),
                }
                for item in indexed
                if item["id"] in records
            ],
        }
    from app.services.embeddings import cosine

    records = (await db.scalars(select(Job).where(available_job_clause()))).all()
    ranked = sorted(
        ((cosine(query_vector, job.embedding), job) for job in records),
        key=lambda item: item[0],
        reverse=True,
    )[:limit]
    return {
        "provider": provider,
        "jobs": [
            {"job": JobOut.model_validate(job), "semantic_score": round(score * 100, 1)}
            for score, job in ranked
        ],
    }


@router.post("/jobs/scan")
async def scan_jobs(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not profile:
        raise HTTPException(404, "Profile not found")
    if not profile.skills:
        raise HTTPException(409, "Upload a resume with recognizable skills before scanning")
    try:
        return await scan_public_jobs(profile, db)
    except Exception as error:
        raise HTTPException(502, f"Public job scan failed: {type(error).__name__}") from None


@router.post("/jobs/import-url", response_model=JobOut, status_code=201)
async def import_job_url(
    data: JobURL, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    try:
        item = await fetch_portal_job(str(data.url))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except Exception as error:
        raise HTTPException(502, f"Job portal lookup failed: {type(error).__name__}") from None
    existing = await db.scalar(
        select(Job).where(Job.source == item["source"], Job.external_id == item["external_id"])
    )
    if existing:
        existing.application_url = item["application_url"]
        profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
        if profile:
            values = calculate_match(profile, existing)
            match_result = await db.scalar(
                select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == existing.id)
            )
            if match_result:
                for key, value in values.items():
                    setattr(match_result, key, value)
            else:
                db.add(JobMatch(user_id=user.id, job_id=existing.id, **values))
            await db.commit()
        return existing
    description = item["description_text"]
    if len(description) < 20:
        raise HTTPException(422, "Job portal returned an incomplete description")
    raw_posted = item.get("posted_at")
    posted_at = datetime.now(UTC).replace(tzinfo=None)
    if isinstance(raw_posted, (int, float)):
        posted_at = datetime.fromtimestamp(raw_posted / 1000, UTC).replace(tzinfo=None)
    elif isinstance(raw_posted, str):
        try:
            posted_at = datetime.fromisoformat(raw_posted).replace(tzinfo=None)
        except ValueError:
            pass
    required = [skill for skill in KNOWN_SKILLS if skill.lower() in description.lower()]
    category, _ = classify(item["title"], description)
    job_embedding, _ = await embed_text(description)
    result = Job(
        external_id=item["external_id"],
        company_name=item["company_name"],
        title=item["title"],
        description=description,
        location=item["location"],
        country="Germany",
        remote_type="unspecified",
        employment_type="unspecified",
        category=category,
        posted_at=posted_at,
        source=item["source"],
        application_url=item["application_url"],
        required_skills=required,
        preferred_skills=[],
        language_requirements={},
        embedding=job_embedding,
    )
    db.add(result)
    await db.flush()
    await vector_upsert("job", result.id, job_embedding, {"title": result.title, "source": result.source})
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile:
        db.add(JobMatch(user_id=user.id, job_id=result.id, **calculate_match(profile, result)))
    await db.commit()
    await db.refresh(result)
    return result


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job(job_id: str, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.get(Job, job_id)
    if not result:
        raise HTTPException(404, "Job not found")
    return result


@router.get("/jobs/{job_id}/application-questions")
async def job_application_questions(
    job_id: str, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    target = await db.get(Job, job_id)
    if not target or is_demo_job(target):
        raise HTTPException(404, "Available job not found")
    try:
        return await fetch_application_questions(target.external_id)
    except Exception as error:
        return {
            "questions": [],
            "source": "employer portal at launch",
            "note": f"The public question schema is temporarily unavailable ({type(error).__name__}). The companion will read the real form before filling.",
        }


@router.post("/jobs/{job_id}/save", response_model=AppOut)
async def save(job_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not await db.get(Job, job_id):
        raise HTTPException(404, "Job not found")
    result = Application(user_id=user.id, job_id=job_id, status=ApplicationStatus.SAVED)
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/jobs/{job_id}/match", response_model=MatchOut)
async def match(job_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    target = await db.get(Job, job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not target or not profile:
        raise HTTPException(404, "Job or profile not found")
    values = calculate_match(profile, target)
    result = await db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job_id))
    if result:
        for key, value in values.items():
            setattr(result, key, value)
    else:
        result = JobMatch(user_id=user.id, job_id=job_id, **values)
        db.add(result)
    await db.commit()
    await db.refresh(result)
    output = MatchOut.model_validate(result)
    return output.model_copy(update={"classification": classification(result.overall_score)})


@router.get("/matches", response_model=list[MatchOut])
async def matches(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return list(
        (
            await db.scalars(
                select(JobMatch)
                .join(Job, Job.id == JobMatch.job_id)
                .where(JobMatch.user_id == user.id, available_job_clause())
                .order_by(desc(JobMatch.overall_score))
            )
        ).all()
    )


@router.post("/applications", response_model=AppOut, status_code=201)
async def create_app(data: AppCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    target = await db.get(Job, data.job_id)
    if not target:
        raise HTTPException(404, "Job not found")
    result = Application(
        user_id=user.id, job_id=data.job_id, notes=data.notes, status=ApplicationStatus.PREPARING
    )
    db.add(result)
    try:
        details = json.loads(data.notes) if data.notes else {}
    except json.JSONDecodeError:
        details = {}
    if details.pop("save_for_future", None):
        excluded = {"truth_confirmation", "review_confirmation"}
        labels_raw = details.pop("_question_labels", {})
        try:
            labels = json.loads(labels_raw) if isinstance(labels_raw, str) else labels_raw
        except json.JSONDecodeError:
            labels = {}
        for key, value in details.items():
            text = str(value).strip()
            if key in excluded or not text:
                continue
            answer = await db.scalar(
                select(CandidateAnswer).where(
                    CandidateAnswer.user_id == user.id, CandidateAnswer.field_key == key
                )
            )
            if answer:
                answer.value = text
                answer.question = str(labels.get(key) or answer.question or key.replace("_", " "))[:500]
            else:
                db.add(
                    CandidateAnswer(
                        user_id=user.id,
                        field_key=key,
                        question=str(labels.get(key) or key.replace("_", " "))[:500],
                        value=text,
                    )
                )
    application_details = {key: value for key, value in details.items() if key != "_question_labels"}
    result.notes = json.dumps(application_details)
    await db.commit()
    await db.refresh(result)
    return result


@router.get("/application-answers")
async def saved_application_answers(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(CandidateAnswer)
            .where(CandidateAnswer.user_id == user.id)
            .order_by(CandidateAnswer.field_key)
        )
    ).all()
    return {
        "answers": {row.field_key: row.value for row in rows},
        "questions": {row.field_key: row.question for row in rows},
    }


@router.put("/application-answers")
async def put_application_answers(
    data: SavedAnswers, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    for key, value in data.answers.items():
        field_key = re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_")[:160]
        text = value.strip()
        if not field_key or not text:
            continue
        answer = await db.scalar(
            select(CandidateAnswer).where(
                CandidateAnswer.user_id == user.id, CandidateAnswer.field_key == field_key
            )
        )
        question = data.questions.get(key) or key.replace("_", " ")
        if answer:
            answer.value = text
            answer.question = question[:500]
        else:
            db.add(CandidateAnswer(user_id=user.id, field_key=field_key, question=question[:500], value=text))
    await db.commit()
    return {"saved": True, "count": len(data.answers)}


@router.get("/applications", response_model=list[AppOut])
async def apps(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return list(
        (
            await db.scalars(
                select(Application)
                .where(Application.user_id == user.id)
                .order_by(desc(Application.updated_at))
            )
        ).all()
    )


@router.patch("/applications/{app_id}", response_model=AppOut)
async def patch_app(
    app_id: str, data: AppPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not result:
        raise HTTPException(404, "Application not found")
    now = datetime.utcnow()
    if data.approved:
        result.approved_at = now
    if data.notes is not None:
        result.notes = data.notes
    if data.status:
        if data.status == ApplicationStatus.APPLIED and not result.approved_at:
            raise HTTPException(409, "Human approval is required before applying")
        result.status = data.status
        if data.status == ApplicationStatus.APPLIED:
            result.applied_at = now
        if data.status == ApplicationStatus.INTERVIEW:
            result.interview_at = now
    result.updated_at = now
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/ai/application")
async def ai_application(
    data: AIRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    application = await db.scalar(
        select(Application).where(Application.id == data.application_id, Application.user_id == user.id)
    )
    if not application:
        raise HTTPException(404, "Application not found")
    target = await db.get(Job, application.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    try:
        details = json.loads(application.notes) if application.notes else {}
    except json.JSONDecodeError:
        details = {"additional_information": application.notes}
    pack = application_pack(profile, target, details)
    generated = await generate_json(
        "application_pack",
        "You prepare truthful job application material. Use only candidate facts in the supplied profile and answers. Never invent skills, employers, dates, degrees, achievements, work authorization, salary, or availability.",
        json.dumps(
            {
                "candidate_profile": {
                    "full_name": profile.full_name,
                    "headline": profile.headline,
                    "skills": profile.skills,
                    "experience": profile.experience,
                    "education": profile.education,
                    "projects": profile.projects,
                    "languages": profile.languages,
                },
                "candidate_answers": details,
                "job": {
                    "title": target.title,
                    "company": target.company_name,
                    "description": target.description,
                    "required_skills": target.required_skills,
                },
                "required_output": {
                    "resume_suggestions": "string",
                    "cover_letter": "string",
                    "recruiter_message": "string",
                    "application_answer": "string",
                },
            },
            default=str,
        ),
    )
    if generated:
        generated_pack, usage = generated
        db.add(ai_usage(user.id, "application_pack", usage))
        for key in pack:
            if isinstance(generated_pack.get(key), str) and generated_pack[key].strip():
                pack[key] = generated_pack[key].strip()
    pack["application_details"] = json.dumps(details, indent=2)
    for kind, content in pack.items():
        latest = (
            await db.scalar(
                select(func.max(ApplicationDocument.version)).where(
                    ApplicationDocument.application_id == application.id,
                    ApplicationDocument.document_type == kind,
                )
            )
            or 0
        )
        db.add(
            ApplicationDocument(
                application_id=application.id, document_type=kind, version=latest + 1, content=content
            )
        )
    application.status = ApplicationStatus.READY
    await db.commit()
    return {"application_id": application.id, "requires_human_approval": True, **pack}


@router.post("/applications/{app_id}/portal-session", status_code=201)
async def create_portal_session(
    app_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    application = await db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not application:
        raise HTTPException(404, "Application not found")
    if application.status != ApplicationStatus.READY:
        raise HTTPException(409, "Generate and review the application before opening the portal")
    target = await db.get(Job, application.job_id)
    if not target or not target.application_url:
        raise HTTPException(404, "Job application URL not found")
    if is_demo_job(target):
        raise HTTPException(
            409,
            "This is a portfolio demo listing and has no employer application portal. Scan or import a real job first.",
        )
    if target.source in {
        "Greenhouse public Job Board API",
        "Lever public Postings API",
        "Ashby public Job Board API",
        "SmartRecruiters public Posting API",
    }:
        try:
            await fetch_portal_job(application_url(target))
        except Exception:
            raise HTTPException(
                410, "This employer posting is no longer available. Refresh Jobs and choose an active role."
            ) from None
    employer_url = application_url(target)
    if employer_url != target.application_url:
        target.application_url = employer_url
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=20)
    db.add(
        PortalSession(
            token_hash=portal_token_hash(token),
            application_id=application.id,
            user_id=user.id,
            expires_at=expires,
        )
    )
    await db.commit()
    portal_url = f"{employer_url.split('#', 1)[0]}#jobflow={token}"
    return {
        "portal_url": portal_url,
        "expires_at": expires,
        "requires_extension": True,
        "requires_human_confirmation": True,
    }


@router.get("/portal-sessions/{token}")
async def get_portal_session(token: str, db: AsyncSession = Depends(get_db)):
    record = await valid_portal_session(token, db)
    application = await db.get(Application, record.application_id)
    target = await db.get(Job, application.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == record.user_id))
    user = await db.get(User, record.user_id)
    try:
        details = json.loads(application.notes) if application.notes else {}
    except json.JSONDecodeError:
        details = {}
    documents = (
        await db.scalars(
            select(ApplicationDocument)
            .where(ApplicationDocument.application_id == application.id)
            .order_by(ApplicationDocument.document_type, ApplicationDocument.version)
        )
    ).all()
    prepared = {document.document_type: document.content for document in documents}
    resume = await db.scalar(
        select(Resume).where(Resume.user_id == record.user_id).order_by(desc(Resume.created_at))
    )
    await db.commit()
    return {
        "application_id": application.id,
        "job": {"title": target.title, "company": target.company_name, "url": target.application_url},
        "candidate": {
            "full_name": details.get("full_name") or profile.full_name,
            "email": details.get("email") or user.email,
            "phone": details.get("phone", ""),
            "address": details.get("address", ""),
            "linkedin": details.get("linkedin", ""),
            "portfolio": details.get("portfolio", ""),
        },
        "answers": details,
        "documents": prepared,
        "resume_available": resume is not None,
        "resume_url": f"/api/v1/portal-sessions/{token}/resume" if resume else None,
        "expires_at": record.expires_at,
        "requires_human_confirmation": True,
    }


@router.get("/applications/{app_id}/documents")
async def application_documents(app_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    application = await db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not application:
        raise HTTPException(404, "Application not found")
    rows = (
        await db.scalars(
            select(ApplicationDocument)
            .where(ApplicationDocument.application_id == app_id)
            .order_by(ApplicationDocument.document_type, desc(ApplicationDocument.version))
        )
    ).all()
    return {
        "documents": [
            {
                "id": row.id,
                "type": row.document_type,
                "version": row.version,
                "content": row.content,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


async def latest_resume_plan(application_id: str, db: AsyncSession) -> dict:
    row = await db.scalar(
        select(ApplicationDocument)
        .where(
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.document_type == "tailored_resume_plan",
        )
        .order_by(desc(ApplicationDocument.version))
    )
    if not row:
        return {}
    try:
        plan = json.loads(row.content)
    except (json.JSONDecodeError, TypeError):
        return {}
    return plan if isinstance(plan, dict) else {}


async def application_resume_context(app_id: str, user: User, db: AsyncSession):
    application = await db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not application:
        raise HTTPException(404, "Application not found")
    target = await db.get(Job, application.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    resume = await db.scalar(
        select(Resume).where(Resume.user_id == user.id).order_by(desc(Resume.created_at))
    )
    if not resume:
        raise HTTPException(404, "Upload a resume before preparing a tailored version")
    return application, target, profile, resume


@router.get("/applications/{app_id}/tailored-resume")
async def application_tailored_resume(
    app_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    application, target, profile, resume = await application_resume_context(app_id, user, db)
    plan = await latest_resume_plan(application.id, db)
    content = tailored_resume_pdf(
        profile,
        resume,
        target,
        selected_line_numbers=plan.get("selected_line_numbers"),
        skill_order=plan.get("skill_order"),
    )
    filename = f"{(profile.full_name or 'candidate').strip().replace(' ', '-')}-tailored.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(len(content)),
            "Cache-Control": "no-store",
        },
    )


@router.post("/applications/{app_id}/tailored-resume/revise")
async def revise_application_resume(
    app_id: str,
    data: ResumeRevisionRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    application, target, profile, resume = await application_resume_context(app_id, user, db)
    source_lines = [line.strip() for line in (resume.extracted_text or "").splitlines() if line.strip()]
    if not source_lines:
        raise HTTPException(422, "The uploaded resume has no extractable text to revise")
    indexed_lines = [{"line_number": index + 1, "text": line} for index, line in enumerate(source_lines)]
    generated = await generate_json(
        "resume_revision",
        "Revise a resume using only the supplied line numbers and exact verified skills. Select and reorder existing lines; never write replacement text or invent facts. Return only line numbers and exact skill strings from the input.",
        json.dumps(
            {
                "revision_request": data.instructions,
                "verified_resume_lines": indexed_lines,
                "verified_skills": profile.skills,
                "job": {
                    "title": target.title,
                    "company": target.company_name,
                    "description": target.description,
                    "required_skills": target.required_skills,
                },
                "required_output": {
                    "selected_line_numbers": "array of existing line_number integers in desired order",
                    "skill_order": "array containing only exact verified_skills strings",
                },
            }
        ),
    )
    raw_plan = generated[0] if generated else {}
    if generated:
        db.add(ai_usage(user.id, "resume_revision", generated[1]))
    requested_numbers = raw_plan.get("selected_line_numbers", [])
    selected_line_numbers = []
    for value in requested_numbers if isinstance(requested_numbers, list) else []:
        if isinstance(value, int) and 1 <= value <= len(source_lines) and value not in selected_line_numbers:
            selected_line_numbers.append(value)
    if not selected_line_numbers:
        terms = set(re.findall(r"[a-z0-9+#.]{2,}", data.instructions.lower()))
        selected_line_numbers = sorted(
            range(1, len(source_lines) + 1),
            key=lambda number: -sum(term in source_lines[number - 1].lower() for term in terms),
        )
    verified_skills = {skill.lower(): skill for skill in profile.skills}
    requested_skills = raw_plan.get("skill_order", [])
    skill_order = []
    for value in requested_skills if isinstance(requested_skills, list) else []:
        if isinstance(value, str) and value.lower() in verified_skills:
            skill = verified_skills[value.lower()]
            if skill not in skill_order:
                skill_order.append(skill)
    if not skill_order:
        skill_order = sorted(
            profile.skills,
            key=lambda skill: (skill.lower() not in data.instructions.lower(), skill.lower()),
        )
    latest = (
        await db.scalar(
            select(func.max(ApplicationDocument.version)).where(
                ApplicationDocument.application_id == application.id,
                ApplicationDocument.document_type == "tailored_resume_plan",
            )
        )
        or 0
    )
    plan = {
        "instructions": data.instructions,
        "selected_line_numbers": selected_line_numbers,
        "skill_order": skill_order,
    }
    db.add(
        ApplicationDocument(
            application_id=application.id,
            document_type="tailored_resume_plan",
            version=latest + 1,
            content=json.dumps(plan),
        )
    )
    await db.commit()
    return {
        "version": latest + 1,
        "message": "Tailored resume updated using verified resume content only.",
        "selected_lines": len(selected_line_numbers),
    }


@router.get("/portal-sessions/{token}/resume")
async def get_portal_resume(token: str, db: AsyncSession = Depends(get_db)):
    record = await valid_portal_session(token, db)
    application = await db.get(Application, record.application_id)
    target = await db.get(Job, application.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == record.user_id))
    resume = await db.scalar(
        select(Resume).where(Resume.user_id == record.user_id).order_by(desc(Resume.created_at))
    )
    if not resume:
        raise HTTPException(404, "Resume not found")
    plan = await latest_resume_plan(application.id, db)
    content = tailored_resume_pdf(
        profile,
        resume,
        target,
        selected_line_numbers=plan.get("selected_line_numbers"),
        skill_order=plan.get("skill_order"),
    )
    await db.commit()
    filename = f"{(profile.full_name or 'candidate').strip().replace(' ', '-')}-tailored.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(len(content)),
        },
    )


@router.post("/portal-sessions/{token}/submitted")
async def portal_submitted(token: str, db: AsyncSession = Depends(get_db)):
    record = await valid_portal_session(token, db)
    application = await db.get(Application, record.application_id)
    now = datetime.utcnow()
    record.submitted_at = now
    application.approved_at = application.approved_at or now
    application.applied_at = now
    application.status = ApplicationStatus.APPLIED
    application.updated_at = now
    await db.commit()
    return {"recorded": True, "application_id": application.id, "status": application.status}


@router.post("/ai/interview")
async def ai_interview(
    data: AIRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    target = await db.get(Job, data.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not target or not profile:
        raise HTTPException(404, "Job or profile not found")
    topics = target.required_skills or [
        skill for skill in KNOWN_SKILLS if skill.lower() in target.description.lower()
    ]
    try:
        questions = await sourced_interview_questions(topics, target.title)
    except Exception:
        questions = []
    preparation = interview_pack(profile, target)
    generated = await generate_json(
        "interview_prep",
        "Create a truthful, company-aware interview plan from the supplied job and candidate facts. Do not invent company facts or candidate experience.",
        json.dumps(
            {
                "candidate": {
                    "skills": profile.skills,
                    "experience": profile.experience,
                    "projects": profile.projects,
                },
                "job": {
                    "title": target.title,
                    "company": target.company_name,
                    "description": target.description,
                    "requirements": target.required_skills,
                },
                "required_output": {
                    "preparation_plan": "string",
                    "behavioral_questions": ["string"],
                    "company_questions": ["string"],
                    "project_talking_points": ["string"],
                },
            },
            default=str,
        ),
    )
    extras = {}
    if generated:
        extras, usage = generated
        db.add(ai_usage(user.id, "interview_prep", usage))
        await db.commit()
        if isinstance(extras.get("preparation_plan"), str):
            preparation = extras.pop("preparation_plan")
    return {
        "job_id": target.id,
        "job_title": target.title,
        "questions": questions,
        "preparation_plan": preparation,
        **extras,
        "source_note": "Technical questions and accepted-answer excerpts come from the public Stack Exchange API and link to their original Stack Overflow pages. Company-specific guidance uses the live job description.",
    }


@router.post("/ai/skills")
async def ai_skills(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    counts = {}
    for result in (await db.scalars(select(JobMatch).where(JobMatch.user_id == user.id))).all():
        for skill in result.missing_skills:
            counts[skill] = counts.get(skill, 0) + 1
    return {
        "top_gaps": [{"skill": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:10]]
    }


@router.post("/ai/job-insights")
async def ai_job_insights(data: AIRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    target = await db.get(Job, data.job_id)
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not target or not profile:
        raise HTTPException(404, "Job or profile not found")
    match_result = await db.scalar(
        select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == target.id)
    )
    matched = match_result.matched_skills if match_result else []
    missing = match_result.missing_skills if match_result else target.required_skills
    recommendations = [
        f"Lead with verified evidence for {', '.join(matched[:4])}."
        if matched
        else "Add relevant verified projects and skills to your profile.",
        f"Prepare an honest example showing how you would learn {missing[0]}."
        if missing
        else "Prepare a concrete project example for the strongest job requirement.",
        "Review the employer's original posting before approving any application answer.",
    ]
    generated = await generate_json(
        "job_insights",
        "Recommend truthful application actions using only supplied facts. Do not invent company or candidate facts.",
        json.dumps(
            {
                "candidate": {"skills": profile.skills, "experience": profile.experience},
                "job": {
                    "title": target.title,
                    "company": target.company_name,
                    "description": target.description,
                },
                "matched_skills": matched,
                "missing_skills": missing,
                "required_output": {"recommendations": ["string"]},
            },
            default=str,
        ),
    )
    provider = "deterministic-fallback"
    if generated:
        content, usage = generated
        candidate = content.get("recommendations")
        if isinstance(candidate, list) and all(isinstance(item, str) for item in candidate):
            recommendations = candidate[:6]
        provider = f"{usage.provider}:{usage.model}"
        db.add(ai_usage(user.id, "job_insights", usage))
        await db.commit()
    return {
        "company": {
            "name": target.company_name,
            "source": target.source,
            "location": target.location,
            "employment_type": target.employment_type,
            "posting_url": target.application_url,
            "posted_at": target.posted_at,
        },
        "recommendations": recommendations,
        "provider": provider,
    }


@router.get("/analytics/skills")
async def analytics_skills(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    strengths = profile.skills if profile else []
    rows = (
        await db.execute(
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(JobMatch.user_id == user.id, available_job_clause())
        )
    ).all()
    demand: dict[str, int] = {}
    gaps: dict[str, int] = {}
    for match_result, target in rows:
        for skill in target.required_skills:
            demand[skill] = demand.get(skill, 0) + 1
        for skill in match_result.missing_skills:
            gaps[skill] = gaps.get(skill, 0) + 1
    denominator = max(1, len(rows))
    skills = [
        {
            "skill": skill,
            "demand": count,
            "percentage": round(count / denominator * 100),
            "gaps": gaps.get(skill, 0),
        }
        for skill, count in sorted(demand.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    top_gaps = [
        {"skill": skill, "count": count, "percentage": round(count / denominator * 100)}
        for skill, count in sorted(gaps.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    return {"skills": skills, "top_gaps": top_gaps, "strengths": strengths, "jobs_analyzed": len(rows)}


@router.get("/analytics/dashboard")
async def dashboard(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    async def count(statement):
        return await db.scalar(statement) or 0

    pipeline = {status.value: 0 for status in ApplicationStatus}
    for status, total in (
        await db.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.user_id == user.id)
            .group_by(Application.status)
        )
    ).all():
        pipeline[status.value] = total
    recent_rows = (
        await db.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.user_id == user.id)
            .order_by(desc(Application.updated_at))
            .limit(5)
        )
    ).all()
    match_rows = (
        await db.execute(
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(JobMatch.user_id == user.id, available_job_clause())
            .order_by(desc(JobMatch.overall_score))
        )
    ).all()
    gap_counts: dict[str, int] = {}
    for match_result, _ in match_rows:
        for skill in match_result.missing_skills:
            gap_counts[skill] = gap_counts.get(skill, 0) + 1
    scored = len(match_rows)
    priority = [
        {
            "id": job.id,
            "title": job.title,
            "company_name": job.company_name,
            "location": job.location,
            "remote_type": job.remote_type,
            "category": job.category,
            "posted_at": job.posted_at,
            "required_skills": job.required_skills,
            "overall_score": match_result.overall_score,
            "matched_skills": match_result.matched_skills,
            "missing_skills": match_result.missing_skills,
        }
        for match_result, job in match_rows[:3]
    ]
    recent = [
        {
            "id": application.id,
            "job_id": job.id,
            "title": job.title,
            "company_name": job.company_name,
            "status": application.status.value,
            "updated_at": application.updated_at,
        }
        for application, job in recent_rows
    ]
    return {
        "total_jobs": await count(select(func.count()).select_from(Job).where(available_job_clause())),
        "new_jobs": await count(
            select(func.count())
            .select_from(Job)
            .where(available_job_clause(), Job.created_at >= datetime.utcnow() - timedelta(days=1))
        ),
        "high_matches": sum(1 for match_result, _ in match_rows if match_result.overall_score >= 80),
        "scored_jobs": scored,
        "applications": sum(pipeline.values()),
        "ready": pipeline[ApplicationStatus.READY.value],
        "interviews": pipeline[ApplicationStatus.INTERVIEW.value],
        "offers": pipeline[ApplicationStatus.OFFER.value],
        "pipeline": pipeline,
        "priority_matches": priority,
        "recent_applications": recent,
        "skill_gaps": [
            {"skill": skill, "count": total, "percentage": round(total / scored * 100) if scored else 0}
            for skill, total in sorted(gap_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
    }


@router.get("/analytics/overview")
async def analytics_overview(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    matches = (await db.scalars(select(JobMatch).where(JobMatch.user_id == user.id))).all()
    applications = (await db.scalars(select(Application).where(Application.user_id == user.id))).all()
    applied = [
        item
        for item in applications
        if item.status
        in {
            ApplicationStatus.APPLIED,
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.OFFER,
            ApplicationStatus.REJECTED,
        }
    ]
    interviews = [
        item for item in applications if item.status in {ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER}
    ]
    now = datetime.utcnow()
    weeks = []
    created = (
        await db.scalars(
            select(Job.created_at).where(Job.created_at >= now - timedelta(weeks=12), available_job_clause())
        )
    ).all()
    for offset in range(11, -1, -1):
        start = now - timedelta(weeks=offset + 1)
        end = now - timedelta(weeks=offset)
        weeks.append(
            {"label": start.strftime("%d %b"), "count": sum(1 for item in created if start <= item < end)}
        )
    usage = (await db.scalars(select(AIUsage).where(AIUsage.user_id == user.id))).all()
    return {
        "match_to_apply_rate": round(len(applications) / len(matches) * 100, 1) if matches else 0,
        "application_to_interview_rate": round(len(interviews) / len(applied) * 100, 1) if applied else 0,
        "average_match": round(sum(item.overall_score for item in matches) / len(matches), 1)
        if matches
        else 0,
        "weekly_jobs": weeks,
        "ai": {
            "requests": len(usage),
            "input_tokens": sum(item.input_tokens for item in usage),
            "output_tokens": sum(item.output_tokens for item in usage),
            "cost_usd": round(sum(item.cost_usd for item in usage), 6),
        },
    }


@router.get("/settings")
async def get_settings(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    preference = await db.get(UserPreference, user.id)
    if not preference:
        preference = UserPreference(user_id=user.id, notification_email=user.email)
        db.add(preference)
        await db.commit()
        await db.refresh(preference)
    return {
        "high_match_email": preference.high_match_email,
        "daily_digest": preference.daily_digest,
        "followup_reminders": preference.followup_reminders,
        "interview_preparation": preference.interview_preparation,
        "notification_email": preference.notification_email,
        "telegram_chat_id": preference.telegram_chat_id,
    }


@router.put("/settings")
async def put_settings(
    data: PreferenceData, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    preference = await db.get(UserPreference, user.id) or UserPreference(user_id=user.id)
    db.add(preference)
    for key, value in data.model_dump().items():
        setattr(preference, key, value or "" if key in {"notification_email", "telegram_chat_id"} else value)
    await db.commit()
    return await get_settings(user, db)


WORKFLOWS = [
    "Candidate Profile Processor",
    "Job Ingestion",
    "Requirement Extractor",
    "Job Matcher",
    "High-match Notification",
    "Application Generator",
    "Follow-up",
    "Interview Prep",
    "Skill Analytics",
    "Global Error Handler",
]


@router.get("/automations")
async def automations(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(WorkflowRun).order_by(desc(WorkflowRun.started_at)).limit(500))).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.workflow, row)
    today = datetime.utcnow().date()
    todays = [row for row in rows if row.started_at.date() == today]
    success = sum(1 for row in todays if row.status.lower() in {"success", "completed"})
    return {
        "executions_today": len(todays),
        "success_rate": round(success / len(todays) * 100, 1) if todays else None,
        "workflows": [
            {
                "id": f"WF-{index:02d}",
                "name": name,
                "status": latest[name].status.upper() if name in latest else "NOT_RUN",
                "last_run": latest[name].started_at if name in latest else None,
                "duration_ms": round(
                    (latest[name].finished_at - latest[name].started_at).total_seconds() * 1000
                )
                if name in latest and latest[name].finished_at
                else None,
                "error": latest[name].error if name in latest else "",
            }
            for index, name in enumerate(WORKFLOWS, 1)
        ],
    }


@router.post("/automations/run-discovery")
async def run_discovery(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not profile or not profile.skills:
        raise HTTPException(409, "Upload a resume with recognizable skills before running discovery")
    started = datetime.utcnow()
    run = WorkflowRun(
        workflow="Job Ingestion",
        status="running",
        input_snapshot={"trigger": "user", "user_id": user.id},
        started_at=started,
    )
    db.add(run)
    await db.commit()
    try:
        result = await scan_public_jobs(profile, db)
        run.status = "success"
        return result
    except Exception as error:
        run.status = "failed"
        run.error = type(error).__name__
        raise HTTPException(502, "Public job discovery failed") from None
    finally:
        run.finished_at = datetime.utcnow()
        workflow_executions.labels(run.workflow, run.status).inc()
        await db.commit()


@router.get("/admin/workflow-runs", dependencies=[Depends(require_role("admin"))])
async def admin_workflow_runs(limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    return list(
        (await db.scalars(select(WorkflowRun).order_by(desc(WorkflowRun.started_at)).limit(limit))).all()
    )


@router.post("/webhooks/n8n/job", dependencies=[Depends(verify_webhook)], status_code=201)
async def ingest(data: JobIn, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(
        select(Job).where(Job.source == data.source, Job.external_id == data.external_id)
    )
    if existing:
        jobs_ingested.labels(data.source, "true").inc()
        return {"id": existing.id, "duplicate": True}
    category, confidence = classify(data.title, data.description)
    values = data.model_dump(exclude={"company", "application_url"})
    embedding, _ = await embed_text(data.description)
    result = Job(
        **values,
        company_name=data.company,
        application_url=str(data.application_url),
        category=category,
        embedding=embedding,
    )
    db.add(result)
    await db.commit()
    await vector_upsert("job", result.id, embedding, {"title": result.title, "source": result.source})
    jobs_ingested.labels(data.source, "false").inc()
    return {"id": result.id, "duplicate": False, "category": category, "confidence": confidence}


async def record(event: Event, db: AsyncSession):
    db.add(
        WorkflowRun(
            workflow=event.workflow,
            execution_id=event.execution_id,
            status=event.status,
            error=event.error,
            input_snapshot=event.payload,
            finished_at=datetime.utcnow(),
        )
    )
    workflow_executions.labels(event.workflow, event.status).inc()
    await db.commit()
    return {"accepted": True}


@router.post("/webhooks/n8n/application", dependencies=[Depends(verify_webhook)])
async def application_event(event: Event, db: AsyncSession = Depends(get_db)):
    return await record(event, db)


@router.post("/webhooks/n8n/status", dependencies=[Depends(verify_webhook)])
async def status_event(event: Event, db: AsyncSession = Depends(get_db)):
    return await record(event, db)


@router.post("/webhooks/n8n/dead-letter", dependencies=[Depends(verify_webhook)], status_code=201)
async def dead_letter(event: Event, db: AsyncSession = Depends(get_db)):
    attempts = int(event.payload.get("attempts", 3))
    severity = str(event.payload.get("severity", "warning"))[:40]
    db.add(
        WorkflowDeadLetter(
            workflow=event.workflow,
            execution_id=event.execution_id,
            error=event.error or "Unknown workflow error",
            severity=severity,
            attempts=attempts,
            input_snapshot=event.payload.get("input", {}),
        )
    )
    workflow_executions.labels(event.workflow, "dead_letter").inc()
    await db.commit()
    return {"accepted": True, "dead_lettered": True}
