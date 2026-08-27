from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from app.services.documents import application_pack, tailored_resume_pdf


def test_application_pack_uses_entered_application_answers():
    profile = SimpleNamespace(full_name="Test Candidate", skills=["Python"])
    job = SimpleNamespace(company_name="Example Co", title="Backend Engineer", description="Python APIs")
    pack = application_pack(
        profile,
        job,
        {
            "motivation": "I value the product mission.",
            "relevant_experience": "I built a verified API project.",
            "achievement": "It reduced processing time by 20%.",
        },
    )
    assert "I value the product mission." in pack["cover_letter"]
    assert "I built a verified API project." in pack["cover_letter"]
    assert pack["application_answer"] == "I value the product mission."


def test_tailored_resume_pdf_uses_only_verified_content():
    profile = SimpleNamespace(
        full_name="Test Candidate", headline="Backend Engineer", skills=["Python", "FastAPI"]
    )
    resume = SimpleNamespace(extracted_text="Test Candidate\nBuilt a verified FastAPI project")
    job = SimpleNamespace(required_skills=["Python", "Kubernetes"], description="Python and Kubernetes role")
    content = tailored_resume_pdf(profile, resume, job)
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_tailored_resume_pdf_applies_verified_line_and_skill_order():
    profile = SimpleNamespace(
        full_name="Test Candidate", headline="Backend Engineer", skills=["Python", "FastAPI"]
    )
    resume = SimpleNamespace(extracted_text="First verified line\nSecond verified FastAPI line")
    job = SimpleNamespace(required_skills=["Python", "FastAPI"], description="Python FastAPI role")
    content = tailored_resume_pdf(
        profile, resume, job, selected_line_numbers=[2, 1, 999], skill_order=["FastAPI", "Invented"]
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    assert text.index("FastAPI, Python") < text.index("Second verified FastAPI line")
    assert text.index("Second verified FastAPI line") < text.index("First verified line")
    assert "Invented" not in text
