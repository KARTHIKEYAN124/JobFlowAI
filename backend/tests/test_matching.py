from datetime import datetime
from types import SimpleNamespace

from app.services.matching import classification, score_match


def test_matching_is_explainable():
    profile = SimpleNamespace(
        skills=["Java", "Spring Boot", "REST", "PostgreSQL", "Docker", "AWS"],
        preferred_roles=["Backend Developer", "Working Student"],
        preferred_locations=["Berlin", "Remote"],
        languages={"English": "Fluent"},
        experience=[{}],
        education=[{}],
        searchable_text="backend java spring boot api docker aws",
    )
    job = SimpleNamespace(
        required_skills=["Java", "Spring Boot", "REST", "PostgreSQL", "AWS", "Docker", "Kafka"],
        title="Backend Working Student",
        category="BACKEND",
        location="Berlin",
        language_requirements={"English": "Fluent"},
        employment_type="working_student",
        posted_at=datetime.now(),
        description="Java Spring Boot REST PostgreSQL AWS Docker Kafka backend",
    )
    result = score_match(profile, job)
    assert result["technical_score"] == 85.7
    assert result["missing_skills"] == ["Kafka"]
    assert result["overall_score"] >= 65


def test_thresholds():
    assert [classification(x) for x in (80, 65, 64.9)] == ["excellent", "good", "low"]
