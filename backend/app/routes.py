import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from pypdf import PdfReader
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import (
    Application,
    ApplicationDocument,
    ApplicationStatus,
    Job,
    JobMatch,
    PortalSession,
    Profile,
    Resume,
    ResumeFile,
    SkillStatistic,
    User,
    WorkflowRun,
    get_db,
)
from app.security import create_token, current_user, hash_password, verify_password, verify_webhook
from app.services.documents import application_pack, interview_pack, tailored_resume_pdf
from app.services.embeddings import embed
from app.services.internet import discover_jobs, fetch_portal_job, sourced_interview_questions
from app.services.jobs import classify, searchable
from app.services.matching import classification, score_match
from app.services.resumes import KNOWN_SKILLS, extract_resume

router=APIRouter(prefix="/api/v1")
class ORM(BaseModel): model_config=ConfigDict(from_attributes=True)
class Register(BaseModel): email:EmailStr; password:str=Field(min_length=10,max_length=128); full_name:str=Field(min_length=2,max_length=160)
class Login(BaseModel): email:EmailStr; password:str
class Token(BaseModel): access_token:str; token_type:str="bearer"
class ProfileData(BaseModel):
    full_name:str=""; headline:str=""; skills:list[str]=Field(default_factory=list); experience:list[dict]=Field(default_factory=list); education:list[dict]=Field(default_factory=list); projects:list[dict]=Field(default_factory=list); languages:dict[str,str]=Field(default_factory=dict); preferred_roles:list[str]=Field(default_factory=list); preferred_locations:list[str]=Field(default_factory=list); expected_salary:str=""; remote_preference:str="hybrid"
class ProfileOut(ProfileData,ORM): id:str; processed_at:datetime|None
class JobIn(BaseModel):
    external_id:str; title:str=Field(min_length=2,max_length=240); company:str=Field(min_length=1,max_length=200); location:str; country:str="Germany"; description:str=Field(min_length=20); employment_type:str="working_student"; remote_type:str="hybrid"; posted_at:datetime; application_url:HttpUrl; source:str; required_skills:list[str]=Field(default_factory=list); preferred_skills:list[str]=Field(default_factory=list); language_requirements:dict[str,str]=Field(default_factory=dict)
class JobURL(BaseModel): url:HttpUrl
class JobOut(ORM):
    id:str; external_id:str; title:str; company_name:str; location:str; country:str; description:str; remote_type:str; employment_type:str; category:str; posted_at:datetime; source:str; application_url:str; required_skills:list; preferred_skills:list
class MatchOut(ORM):
    id:str; job_id:str; overall_score:float; technical_score:float; semantic_score:float; matched_skills:list; missing_skills:list; explanation:str; classification:str=""
class AppCreate(BaseModel): job_id:str; notes:str=""
class AppPatch(BaseModel): status:ApplicationStatus|None=None; notes:str|None=None; approved:bool|None=None
class AppOut(ORM): id:str; job_id:str; status:ApplicationStatus; applied_at:datetime|None; interview_at:datetime|None; followup_at:datetime|None; notes:str; approved_at:datetime|None; created_at:datetime
class AIRequest(BaseModel): application_id:str|None=None; job_id:str|None=None; question:str|None=None
class Event(BaseModel): workflow:str; execution_id:str=""; status:str="success"; payload:dict[str,Any]=Field(default_factory=dict); error:str=""


def portal_token_hash(token:str) -> str: return hashlib.sha256(token.encode()).hexdigest()
async def valid_portal_session(token:str,db:AsyncSession) -> PortalSession:
    record=await db.scalar(select(PortalSession).where(PortalSession.token_hash==portal_token_hash(token)))
    if not record: raise HTTPException(404,"Portal session not found")
    if record.expires_at<datetime.utcnow(): raise HTTPException(410,"Portal session expired")
    record.last_used_at=datetime.utcnow(); return record


async def scan_public_jobs(profile:Profile,db:AsyncSession) -> dict:
    discovered=await discover_jobs(profile.skills,profile.preferred_roles)
    imported=0
    matched=0
    for item in discovered:
        external_id=str(item["slug"])
        source=item.get("source") or "Public job feed"
        target=await db.scalar(select(Job).where(Job.source==source,Job.external_id==external_id))
        if not target:
            description=item["description_text"]
            required=[skill for skill in KNOWN_SKILLS if skill.lower() in description.lower()]
            category,_=classify(item.get("title", ""),description)
            created_at=item.get("created_at") or 0
            posted_at=datetime.fromtimestamp(created_at,UTC).replace(tzinfo=None) if created_at else datetime.now(UTC).replace(tzinfo=None)
            target=Job(
                external_id=external_id,company_name=item.get("company_name") or "Unknown company",
                title=item.get("title") or "Untitled role",description=description,
                location=item.get("location") or ("Remote" if item.get("remote") else "Germany"),
                remote_type="remote" if item.get("remote") else "onsite",
                employment_type=(item.get("job_types") or ["unspecified"])[0],category=category,
                posted_at=posted_at,source=source,
                application_url=item.get("url") or "https://www.arbeitnow.com/",
                required_skills=required,preferred_skills=item.get("tags") or [],
                language_requirements={},embedding=embed(description),
            )
            db.add(target); await db.flush(); imported+=1
        values=score_match(profile,target)
        match_result=await db.scalar(select(JobMatch).where(JobMatch.user_id==profile.user_id,JobMatch.job_id==target.id))
        if match_result:
            for key,value in values.items(): setattr(match_result,key,value)
        else: db.add(JobMatch(user_id=profile.user_id,job_id=target.id,**values))
        matched+=1
    await db.commit()
    sources=sorted({item.get("source") or "Public job feed" for item in discovered})
    return {"source":", ".join(sources) or "public job feeds","sources":sources,"found":len(discovered),"imported":imported,"matched":matched,"skills_used":profile.skills}

@router.post("/auth/register",response_model=Token,status_code=201)
async def register(data:Register,db:AsyncSession=Depends(get_db)):
    user=User(email=data.email.lower(),password_hash=hash_password(data.password)); db.add(user)
    try: await db.flush()
    except IntegrityError: await db.rollback(); raise HTTPException(409,"Email already registered") from None
    db.add(Profile(user_id=user.id,full_name=data.full_name)); await db.commit(); return Token(access_token=create_token(user))
@router.post("/auth/login",response_model=Token)
async def login(data:Login,db:AsyncSession=Depends(get_db)):
    user=await db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"Invalid credentials")
    return Token(access_token=create_token(user))
@router.get("/profile",response_model=ProfileOut)
async def get_profile(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    result=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if not result: raise HTTPException(404,"Profile not found")
    return result
@router.put("/profile",response_model=ProfileOut)
async def put_profile(data:ProfileData,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    profile=await db.scalar(select(Profile).where(Profile.user_id==user.id)) or Profile(user_id=user.id); db.add(profile)
    values=data.model_dump()
    for key,value in values.items(): setattr(profile,key,value)
    profile.searchable_text=searchable(values); profile.embedding=embed(profile.searchable_text); profile.processed_at=datetime.utcnow(); await db.commit(); await db.refresh(profile); return profile
@router.post("/resume",status_code=201)
async def post_resume(file:UploadFile=File(...),user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    if file.content_type!="application/pdf" or not (file.filename or "").lower().endswith(".pdf"): raise HTTPException(415,"Only PDF resumes are accepted")
    content=await file.read(settings.max_resume_bytes+1)
    if len(content)>settings.max_resume_bytes: raise HTTPException(413,"Resume exceeds 5 MB")
    try: text="\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    except Exception: raise HTTPException(422,"Unreadable PDF") from None
    if not text.strip(): raise HTTPException(422,"PDF contains no extractable text")
    structured=extract_resume(text); resume=Resume(user_id=user.id,filename=file.filename or "resume.pdf",content_type=file.content_type,extracted_text=text,structured_data=structured); db.add(resume)
    await db.flush()
    db.add(ResumeFile(resume_id=resume.id,data=content,size=len(content)))
    profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if profile:
        profile.skills=list(dict.fromkeys([*profile.skills,*structured["skills"]]))
        profile.searchable_text=" ".join([profile.full_name,profile.headline,*profile.skills,*profile.preferred_roles,*profile.preferred_locations])
        profile.embedding=embed(profile.searchable_text); profile.processed_at=datetime.utcnow()
    await db.commit()
    try: job_scan=await scan_public_jobs(profile,db) if profile else {"found":0,"imported":0,"matched":0,"skills_used":[]}
    except Exception as error: job_scan={"found":0,"imported":0,"matched":0,"skills_used":structured["skills"],"error":f"Public job scan unavailable: {type(error).__name__}"}
    return {"id":resume.id,"filename":resume.filename,"characters":len(text),"structured_data":structured,"created_at":resume.created_at,"stored":True,"file_size":len(content),"download_url":"/api/v1/resume/file","job_scan":job_scan}
@router.get("/resume")
async def get_resume(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    resume=await db.scalar(select(Resume).where(Resume.user_id==user.id).order_by(desc(Resume.created_at)))
    if not resume: raise HTTPException(404,"Resume not found")
    stored=await db.get(ResumeFile,resume.id)
    return {"id":resume.id,"filename":resume.filename,"structured_data":resume.structured_data,"created_at":resume.created_at,"stored":stored is not None,"file_size":stored.size if stored else None,"download_url":"/api/v1/resume/file" if stored else None}
@router.get("/resume/file")
async def get_resume_file(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(select(Resume,ResumeFile).join(ResumeFile,ResumeFile.resume_id==Resume.id).where(Resume.user_id==user.id).order_by(desc(Resume.created_at)).limit(1))).first()
    if not row: raise HTTPException(404,"Stored resume PDF not found")
    resume,stored=row
    return Response(content=stored.data,media_type=resume.content_type,headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(resume.filename)}","Content-Length":str(stored.size)})
@router.get("/jobs",response_model=list[JobOut])
async def jobs(q:str="",location:str="",category:str="",remote:str="",minimum_match:float=Query(0,ge=0,le=100),limit:int=Query(50,ge=1,le=100),user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    statement=select(Job).order_by(desc(Job.posted_at)).limit(limit)
    if q: statement=statement.where(or_(Job.title.ilike(f"%{q}%"),Job.company_name.ilike(f"%{q}%")))
    if location: statement=statement.where(Job.location.ilike(f"%{location}%"))
    if category: statement=statement.where(Job.category==category.upper())
    if remote: statement=statement.where(Job.remote_type==remote)
    if minimum_match: statement=statement.join(JobMatch).where(JobMatch.user_id==user.id,JobMatch.overall_score>=minimum_match)
    return list((await db.scalars(statement)).all())
@router.post("/jobs/scan")
async def scan_jobs(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if not profile: raise HTTPException(404,"Profile not found")
    if not profile.skills: raise HTTPException(409,"Upload a resume with recognizable skills before scanning")
    try: return await scan_public_jobs(profile,db)
    except Exception as error: raise HTTPException(502,f"Public job scan failed: {type(error).__name__}") from None
@router.post("/jobs/import-url",response_model=JobOut,status_code=201)
async def import_job_url(data:JobURL,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    try: item=await fetch_portal_job(str(data.url))
    except ValueError as error: raise HTTPException(422,str(error)) from None
    except Exception as error: raise HTTPException(502,f"Job portal lookup failed: {type(error).__name__}") from None
    existing=await db.scalar(select(Job).where(Job.source==item["source"],Job.external_id==item["external_id"]))
    if existing:
        profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
        if profile:
            values=score_match(profile,existing)
            match_result=await db.scalar(select(JobMatch).where(JobMatch.user_id==user.id,JobMatch.job_id==existing.id))
            if match_result:
                for key,value in values.items(): setattr(match_result,key,value)
            else: db.add(JobMatch(user_id=user.id,job_id=existing.id,**values))
            await db.commit()
        return existing
    description=item["description_text"]
    if len(description)<20: raise HTTPException(422,"Job portal returned an incomplete description")
    raw_posted=item.get("posted_at"); posted_at=datetime.now(UTC).replace(tzinfo=None)
    if isinstance(raw_posted,(int,float)): posted_at=datetime.fromtimestamp(raw_posted/1000,UTC).replace(tzinfo=None)
    elif isinstance(raw_posted,str):
        try: posted_at=datetime.fromisoformat(raw_posted).replace(tzinfo=None)
        except ValueError: pass
    required=[skill for skill in KNOWN_SKILLS if skill.lower() in description.lower()]
    category,_=classify(item["title"],description)
    result=Job(external_id=item["external_id"],company_name=item["company_name"],title=item["title"],description=description,location=item["location"],country="Germany",remote_type="unspecified",employment_type="unspecified",category=category,posted_at=posted_at,source=item["source"],application_url=item["application_url"],required_skills=required,preferred_skills=[],language_requirements={},embedding=embed(description)); db.add(result); await db.flush()
    profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if profile: db.add(JobMatch(user_id=user.id,job_id=result.id,**score_match(profile,result)))
    await db.commit(); await db.refresh(result); return result
@router.get("/jobs/{job_id}",response_model=JobOut)
async def job(job_id:str,_:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    result=await db.get(Job,job_id)
    if not result: raise HTTPException(404,"Job not found")
    return result
@router.post("/jobs/{job_id}/save",response_model=AppOut)
async def save(job_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    if not await db.get(Job,job_id): raise HTTPException(404,"Job not found")
    result=Application(user_id=user.id,job_id=job_id,status=ApplicationStatus.SAVED); db.add(result); await db.commit(); await db.refresh(result); return result
@router.post("/jobs/{job_id}/match",response_model=MatchOut)
async def match(job_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    target=await db.get(Job,job_id); profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if not target or not profile: raise HTTPException(404,"Job or profile not found")
    values=score_match(profile,target); result=await db.scalar(select(JobMatch).where(JobMatch.user_id==user.id,JobMatch.job_id==job_id))
    if result:
        for key,value in values.items(): setattr(result,key,value)
    else: result=JobMatch(user_id=user.id,job_id=job_id,**values); db.add(result)
    await db.commit(); await db.refresh(result); output=MatchOut.model_validate(result); return output.model_copy(update={"classification":classification(result.overall_score)})
@router.get("/matches",response_model=list[MatchOut])
async def matches(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)): return list((await db.scalars(select(JobMatch).where(JobMatch.user_id==user.id).order_by(desc(JobMatch.overall_score)))).all())
@router.post("/applications",response_model=AppOut,status_code=201)
async def create_app(data:AppCreate,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    if not await db.get(Job,data.job_id): raise HTTPException(404,"Job not found")
    result=Application(user_id=user.id,job_id=data.job_id,notes=data.notes,status=ApplicationStatus.PREPARING); db.add(result); await db.commit(); await db.refresh(result); return result
@router.get("/applications",response_model=list[AppOut])
async def apps(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)): return list((await db.scalars(select(Application).where(Application.user_id==user.id).order_by(desc(Application.updated_at)))).all())
@router.patch("/applications/{app_id}",response_model=AppOut)
async def patch_app(app_id:str,data:AppPatch,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    result=await db.scalar(select(Application).where(Application.id==app_id,Application.user_id==user.id))
    if not result: raise HTTPException(404,"Application not found")
    now=datetime.utcnow()
    if data.approved: result.approved_at=now
    if data.notes is not None: result.notes=data.notes
    if data.status:
        if data.status==ApplicationStatus.APPLIED and not result.approved_at: raise HTTPException(409,"Human approval is required before applying")
        result.status=data.status
        if data.status==ApplicationStatus.APPLIED: result.applied_at=now
        if data.status==ApplicationStatus.INTERVIEW: result.interview_at=now
    result.updated_at=now; await db.commit(); await db.refresh(result); return result
@router.post("/ai/application")
async def ai_application(data:AIRequest,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    application=await db.scalar(select(Application).where(Application.id==data.application_id,Application.user_id==user.id))
    if not application: raise HTTPException(404,"Application not found")
    target=await db.get(Job,application.job_id); profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    try: details=json.loads(application.notes) if application.notes else {}
    except json.JSONDecodeError: details={"additional_information":application.notes}
    pack=application_pack(profile,target,details); pack["application_details"]=json.dumps(details,indent=2)
    for kind,content in pack.items(): db.add(ApplicationDocument(application_id=application.id,document_type=kind,content=content))
    application.status=ApplicationStatus.READY; await db.commit(); return {"application_id":application.id,"requires_human_approval":True,**pack}
@router.post("/applications/{app_id}/portal-session",status_code=201)
async def create_portal_session(app_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    application=await db.scalar(select(Application).where(Application.id==app_id,Application.user_id==user.id))
    if not application: raise HTTPException(404,"Application not found")
    if application.status!=ApplicationStatus.READY: raise HTTPException(409,"Generate and review the application before opening the portal")
    target=await db.get(Job,application.job_id)
    if not target or not target.application_url: raise HTTPException(404,"Job application URL not found")
    token=secrets.token_urlsafe(32); expires=datetime.utcnow()+timedelta(minutes=20)
    db.add(PortalSession(token_hash=portal_token_hash(token),application_id=application.id,user_id=user.id,expires_at=expires)); await db.commit()
    portal_url=f"{target.application_url.split('#',1)[0]}#jobflow={token}"
    return {"portal_url":portal_url,"expires_at":expires,"requires_extension":True,"requires_human_confirmation":True}
@router.get("/portal-sessions/{token}")
async def get_portal_session(token:str,db:AsyncSession=Depends(get_db)):
    record=await valid_portal_session(token,db); application=await db.get(Application,record.application_id); target=await db.get(Job,application.job_id); profile=await db.scalar(select(Profile).where(Profile.user_id==record.user_id)); user=await db.get(User,record.user_id)
    try: details=json.loads(application.notes) if application.notes else {}
    except json.JSONDecodeError: details={}
    documents=(await db.scalars(select(ApplicationDocument).where(ApplicationDocument.application_id==application.id).order_by(desc(ApplicationDocument.created_at)))).all()
    prepared={document.document_type:document.content for document in documents}
    resume=await db.scalar(select(Resume).where(Resume.user_id==record.user_id).order_by(desc(Resume.created_at)))
    await db.commit()
    return {"application_id":application.id,"job":{"title":target.title,"company":target.company_name,"url":target.application_url},"candidate":{"full_name":details.get("full_name") or profile.full_name,"email":details.get("email") or user.email,"phone":details.get("phone","") ,"address":details.get("address","") ,"linkedin":details.get("linkedin","") ,"portfolio":details.get("portfolio","")},"answers":details,"documents":prepared,"resume_available":resume is not None,"resume_url":f"/api/v1/portal-sessions/{token}/resume" if resume else None,"expires_at":record.expires_at,"requires_human_confirmation":True}
@router.get("/portal-sessions/{token}/resume")
async def get_portal_resume(token:str,db:AsyncSession=Depends(get_db)):
    record=await valid_portal_session(token,db); application=await db.get(Application,record.application_id); target=await db.get(Job,application.job_id); profile=await db.scalar(select(Profile).where(Profile.user_id==record.user_id)); resume=await db.scalar(select(Resume).where(Resume.user_id==record.user_id).order_by(desc(Resume.created_at)))
    if not resume: raise HTTPException(404,"Resume not found")
    content=tailored_resume_pdf(profile,resume,target); await db.commit(); filename=f"{(profile.full_name or 'candidate').strip().replace(' ','-')}-tailored.pdf"
    return Response(content=content,media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(filename)}","Content-Length":str(len(content))})
@router.post("/portal-sessions/{token}/submitted")
async def portal_submitted(token:str,db:AsyncSession=Depends(get_db)):
    record=await valid_portal_session(token,db); application=await db.get(Application,record.application_id); now=datetime.utcnow(); record.submitted_at=now; application.approved_at=application.approved_at or now; application.applied_at=now; application.status=ApplicationStatus.APPLIED; application.updated_at=now; await db.commit(); return {"recorded":True,"application_id":application.id,"status":application.status}
@router.post("/ai/interview")
async def ai_interview(data:AIRequest,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    target=await db.get(Job,data.job_id); profile=await db.scalar(select(Profile).where(Profile.user_id==user.id))
    if not target or not profile: raise HTTPException(404,"Job or profile not found")
    topics=target.required_skills or [skill for skill in KNOWN_SKILLS if skill.lower() in target.description.lower()]
    try: questions=await sourced_interview_questions(topics,target.title)
    except Exception: questions=[]
    return {"job_id":target.id,"job_title":target.title,"questions":questions,"preparation_plan":interview_pack(profile,target),"source_note":"Questions and accepted-answer excerpts come from the public Stack Exchange API and link to their original Stack Overflow pages."}
@router.post("/ai/skills")
async def ai_skills(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    counts={}
    for result in (await db.scalars(select(JobMatch).where(JobMatch.user_id==user.id))).all():
        for skill in result.missing_skills: counts[skill]=counts.get(skill,0)+1
    return {"top_gaps":[{"skill":k,"count":v} for k,v in sorted(counts.items(),key=lambda x:-x[1])[:10]]}
@router.get("/analytics/skills")
async def analytics_skills(_:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    rows=(await db.scalars(select(SkillStatistic).order_by(desc(SkillStatistic.demand_count)).limit(20))).all(); return {"skills":[{"skill":x.skill,"demand":x.demand_count,"gaps":x.gap_count} for x in rows]}
@router.get("/analytics/dashboard")
async def dashboard(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    async def count(statement): return await db.scalar(statement) or 0
    pipeline={status.value:0 for status in ApplicationStatus}
    for status,total in (await db.execute(select(Application.status,func.count(Application.id)).where(Application.user_id==user.id).group_by(Application.status))).all(): pipeline[status.value]=total
    recent_rows=(await db.execute(select(Application,Job).join(Job,Job.id==Application.job_id).where(Application.user_id==user.id).order_by(desc(Application.updated_at)).limit(5))).all()
    match_rows=(await db.execute(select(JobMatch,Job).join(Job,Job.id==JobMatch.job_id).where(JobMatch.user_id==user.id).order_by(desc(JobMatch.overall_score)))).all()
    gap_counts:dict[str,int]={}
    for match_result,_ in match_rows:
        for skill in match_result.missing_skills: gap_counts[skill]=gap_counts.get(skill,0)+1
    scored=len(match_rows)
    priority=[{"id":job.id,"title":job.title,"company_name":job.company_name,"location":job.location,"remote_type":job.remote_type,"category":job.category,"posted_at":job.posted_at,"required_skills":job.required_skills,"overall_score":match_result.overall_score,"matched_skills":match_result.matched_skills,"missing_skills":match_result.missing_skills} for match_result,job in match_rows[:3]]
    recent=[{"id":application.id,"job_id":job.id,"title":job.title,"company_name":job.company_name,"status":application.status.value,"updated_at":application.updated_at} for application,job in recent_rows]
    return {
        "total_jobs":await count(select(func.count()).select_from(Job)),
        "new_jobs":await count(select(func.count()).select_from(Job).where(Job.created_at>=datetime.utcnow()-timedelta(days=1))),
        "high_matches":sum(1 for match_result,_ in match_rows if match_result.overall_score>=80),
        "scored_jobs":scored,"applications":sum(pipeline.values()),"ready":pipeline[ApplicationStatus.READY.value],
        "interviews":pipeline[ApplicationStatus.INTERVIEW.value],"offers":pipeline[ApplicationStatus.OFFER.value],
        "pipeline":pipeline,"priority_matches":priority,"recent_applications":recent,
        "skill_gaps":[{"skill":skill,"count":total,"percentage":round(total/scored*100) if scored else 0} for skill,total in sorted(gap_counts.items(),key=lambda item:(-item[1],item[0]))[:5]],
    }
@router.post("/webhooks/n8n/job",dependencies=[Depends(verify_webhook)],status_code=201)
async def ingest(data:JobIn,db:AsyncSession=Depends(get_db)):
    existing=await db.scalar(select(Job).where(Job.source==data.source,Job.external_id==data.external_id))
    if existing: return {"id":existing.id,"duplicate":True}
    category,confidence=classify(data.title,data.description); values=data.model_dump(exclude={"company","application_url"}); result=Job(**values,company_name=data.company,application_url=str(data.application_url),category=category,embedding=embed(data.description)); db.add(result); await db.commit(); return {"id":result.id,"duplicate":False,"category":category,"confidence":confidence}
async def record(event:Event,db:AsyncSession): db.add(WorkflowRun(workflow=event.workflow,execution_id=event.execution_id,status=event.status,error=event.error,input_snapshot=event.payload,finished_at=datetime.utcnow())); await db.commit(); return {"accepted":True}
@router.post("/webhooks/n8n/application",dependencies=[Depends(verify_webhook)])
async def application_event(event:Event,db:AsyncSession=Depends(get_db)): return await record(event,db)
@router.post("/webhooks/n8n/status",dependencies=[Depends(verify_webhook)])
async def status_event(event:Event,db:AsyncSession=Depends(get_db)): return await record(event,db)
