from types import SimpleNamespace

from app.services.documents import application_pack


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
