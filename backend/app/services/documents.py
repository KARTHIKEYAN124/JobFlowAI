from html import escape
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def application_pack(profile, job, details=None):
    details = details or {}
    skills = [s for s in profile.skills if s.lower() in job.description.lower()]
    emphasized = ", ".join(skills[:8]) or ", ".join(profile.skills[:6])
    name = profile.full_name or "Candidate"
    motivation = (
        details.get("motivation") or f"The role connects directly to my verified experience in {emphasized}."
    )
    experience = (
        details.get("relevant_experience") or f"My experience with {emphasized} aligns well with the role."
    )
    achievement = details.get("achievement") or ""
    evidence = f" {achievement}" if achievement else ""
    return {
        "resume_suggestions": f"Lead with {emphasized}. Reorder only existing evidence; never add unverified claims.",
        "cover_letter": f"Dear {job.company_name} hiring team,\n\nI am applying for {job.title}. {motivation}\n\n{experience}{evidence}\n\nSincerely,\n{name}",
        "recruiter_message": f"Hello, I am interested in {job.title} at {job.company_name}. My background in {emphasized} appears closely aligned.",
        "application_answer": motivation,
    }


def interview_pack(profile, job):
    gaps = [s for s in job.required_skills if s.lower() not in {x.lower() for x in profile.skills}]
    return "\n".join(
        [
            f"Technical concepts: {', '.join(job.required_skills) or 'role fundamentals'}",
            f"Review gaps: {', '.join(gaps) or 'none'}",
            "Coding: prepare one implementation and one debugging example.",
            "Behavioral: ownership, collaboration, learning, and trade-offs.",
            f"Ask how success for {job.title} is measured in the first 90 days.",
        ]
    )


def tailored_resume_pdf(profile, resume, job, selected_line_numbers=None, skill_order=None):
    """Create an ATS-readable PDF that only reorders verified candidate content."""
    verified = {skill.lower(): skill for skill in profile.skills}
    relevant = [verified[skill.lower()] for skill in job.required_skills if skill.lower() in verified]
    if not relevant:
        relevant = [skill for skill in profile.skills if skill.lower() in job.description.lower()]
    if skill_order:
        requested = [verified[skill.lower()] for skill in skill_order if skill.lower() in verified]
        relevant = requested + [skill for skill in relevant if skill.lower() not in {item.lower() for item in requested}]
    source_lines = [line.strip() for line in (resume.extracted_text or "").splitlines() if line.strip()]
    if selected_line_numbers:
        seen = set()
        selected_lines = []
        for number in selected_line_numbers:
            if isinstance(number, int) and 1 <= number <= len(source_lines) and number not in seen:
                selected_lines.append(source_lines[number - 1])
                seen.add(number)
        if selected_lines:
            source_lines = selected_lines
    styles = getSampleStyleSheet()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{profile.full_name or 'Candidate'} - tailored resume",
    )
    story = [Paragraph(escape(profile.full_name or "Candidate"), styles["Title"])]
    if profile.headline:
        story.extend([Paragraph(escape(profile.headline), styles["Heading2"]), Spacer(1, 4 * mm)])
    story.extend(
        [
            Paragraph("Relevant verified skills", styles["Heading2"]),
            Paragraph(
                escape(", ".join(relevant) or "See verified resume content below."), styles["BodyText"]
            ),
            Spacer(1, 5 * mm),
            Paragraph("Verified resume content", styles["Heading2"]),
        ]
    )
    for line in source_lines:
        story.extend([Paragraph(escape(line), styles["BodyText"]), Spacer(1, 1.5 * mm)])
    document.build(story)
    return output.getvalue()
