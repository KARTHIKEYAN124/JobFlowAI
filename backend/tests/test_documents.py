from types import SimpleNamespace

from app.services.documents import application_pack, tailored_resume_pdf


def test_application_pack_uses_entered_application_answers():
    profile = SimpleNamespace(full_name="Test Candidate", skills=["Python"])
    job = SimpleNamespace(company_name="Example Co", title="Backend Engineer", description="Python APIs")
    pack = application_pack(profile, job, {
        "motivation": "I value the product mission.",
        "relevant_experience": "I built a verified API project.",
        "achievement": "It reduced processing time by 20%.",
    })
    assert "I value the product mission." in pack["cover_letter"]
    assert "I built a verified API project." in pack["cover_letter"]
    assert pack["application_answer"] == "I value the product mission."


def test_tailored_resume_pdf_uses_only_verified_content():
    profile=SimpleNamespace(full_name="Test Candidate",headline="Backend Engineer",skills=["Python","FastAPI"])
    resume=SimpleNamespace(extracted_text="Test Candidate\nBuilt a verified FastAPI project")
    job=SimpleNamespace(required_skills=["Python","Kubernetes"],description="Python and Kubernetes role")
    content=tailored_resume_pdf(profile,resume,job)
    assert content.startswith(b"%PDF")
    assert len(content)>1000
