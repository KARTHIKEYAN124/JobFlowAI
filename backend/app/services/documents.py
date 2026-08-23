def application_pack(profile,job,details=None):
    details=details or {}
    skills=[s for s in profile.skills if s.lower() in job.description.lower()]; emphasized=", ".join(skills[:8]) or ", ".join(profile.skills[:6]); name=profile.full_name or "Candidate"
    motivation=details.get("motivation") or f"The role connects directly to my verified experience in {emphasized}."
    experience=details.get("relevant_experience") or f"My experience with {emphasized} aligns well with the role."
    achievement=details.get("achievement") or ""
    evidence=f" {achievement}" if achievement else ""
    return {"resume_suggestions":f"Lead with {emphasized}. Reorder only existing evidence; never add unverified claims.","cover_letter":f"Dear {job.company_name} hiring team,\n\nI am applying for {job.title}. {motivation}\n\n{experience}{evidence}\n\nSincerely,\n{name}","recruiter_message":f"Hello, I am interested in {job.title} at {job.company_name}. My background in {emphasized} appears closely aligned.","application_answer":motivation}
def interview_pack(profile,job):
    gaps=[s for s in job.required_skills if s.lower() not in {x.lower() for x in profile.skills}]
    return "\n".join([f"Technical concepts: {', '.join(job.required_skills) or 'role fundamentals'}",f"Review gaps: {', '.join(gaps) or 'none'}","Coding: prepare one implementation and one debugging example.","Behavioral: ownership, collaboration, learning, and trade-offs.",f"Ask how success for {job.title} is measured in the first 90 days."])
