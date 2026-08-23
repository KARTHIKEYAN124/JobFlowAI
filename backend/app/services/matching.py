import math
import re
from datetime import datetime

from app.services.embeddings import cosine


def normalized(values): return {re.sub(r"[^a-z0-9+#.]","",v.lower()):v for v in values}
def similarity(left,right):
    a=set(re.findall(r"[a-z0-9+#.]+",left.lower())); b=set(re.findall(r"[a-z0-9+#.]+",right.lower()))
    return len(a&b)/math.sqrt(len(a)*len(b)) if a and b else 0.0


def score_match(profile,job):
    candidate=normalized(profile.skills); required=normalized(job.required_skills); keys=candidate.keys()&required.keys()
    matched=[required[k] for k in keys]; missing=[v for k,v in required.items() if k not in candidate]
    technical=len(matched)/len(required) if required else 1.0
    role=similarity(" ".join(profile.preferred_roles),f"{job.title} {job.category}")
    profile_embedding = getattr(profile, "embedding", [])
    job_embedding = getattr(job, "embedding", [])
    semantic=cosine(profile_embedding,job_embedding) if profile_embedding and job_embedding else similarity(profile.searchable_text or " ".join(profile.skills),job.description)
    location=1.0 if any(x.lower() in job.location.lower() for x in profile.preferred_locations) else .4
    required_languages={x.lower() for x in job.language_requirements}; languages={x.lower() for x in profile.languages}
    language=len(required_languages&languages)/len(required_languages) if required_languages else 1.0
    experience=1.0 if profile.experience else .6; education=1.0 if profile.education else .6
    freshness=max(0.0,1-max(0,(datetime.now()-job.posted_at).days)/30)
    employment=1.0 if job.employment_type.lower() in " ".join(profile.preferred_roles).lower() else .75
    deterministic=technical*40+role*20+experience*10+education*10+location*5+language*5+freshness*5+employment*5
    overall=min(100.0,round(.65*deterministic+.35*semantic*100,1))
    strongest=", ".join(matched[:6]) or "transferable experience"; gap=", ".join(missing[:3]) or "no major technical gaps"
    return dict(overall_score=overall,technical_score=round(technical*100,1),semantic_score=round(semantic*100,1),role_score=round(role*100,1),location_score=round(location*100,1),experience_score=round(experience*100,1),education_score=round(education*100,1),language_score=round(language*100,1),freshness_score=round(freshness*100,1),employment_score=round(employment*100,1),matched_skills=matched,missing_skills=missing,explanation=f"Strongest overlap: {strongest}. Primary gap: {gap}.")


def classification(score): return "excellent" if score>=80 else "good" if score>=65 else "low"
