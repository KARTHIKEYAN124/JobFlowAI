import uuid

from fastapi.testclient import TestClient

from app import routes
from app.main import app


def test_health_and_security_headers():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "jobflow-api"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_protected_route_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/profile")
    assert response.status_code == 401


def test_webhook_rejects_unsigned_requests():
    with TestClient(app) as client:
        response = client.post("/api/v1/webhooks/n8n/status", json={"workflow": "test"})
    assert response.status_code == 401


def test_uploaded_resume_pdf_is_stored_and_downloadable(monkeypatch):
    pdf_content = b"%PDF-1.4\nJobFlow persistence verification\n%%EOF"

    class ParsedPage:
        @staticmethod
        def extract_text():
            return "Python FastAPI PostgreSQL backend engineer"

    monkeypatch.setattr(routes, "PdfReader", lambda _: type("ParsedPdf", (), {"pages": [ParsedPage()]})())

    async def no_external_scan(*_):
        return {"source": "test", "found": 0, "imported": 0, "matched": 0, "skills_used": ["Python"]}

    monkeypatch.setattr(routes, "scan_public_jobs", no_external_scan)

    with TestClient(app) as client:
        email = f"resume-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Resume Test"},
        )
        token = registration.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        uploaded = client.post(
            "/api/v1/resume",
            headers=headers,
            files={"file": ("candidate.pdf", pdf_content, "application/pdf")},
        )
        assert uploaded.status_code == 201
        assert uploaded.json()["stored"] is True
        assert uploaded.json()["file_size"] == len(pdf_content)

        metadata = client.get("/api/v1/resume", headers=headers)
        assert metadata.status_code == 200
        assert metadata.json()["filename"] == "candidate.pdf"
        assert metadata.json()["stored"] is True

        downloaded = client.get("/api/v1/resume/file", headers=headers)
        assert downloaded.status_code == 200
        assert downloaded.content == pdf_content
        assert downloaded.headers["content-type"] == "application/pdf"
        assert "candidate.pdf" in downloaded.headers["content-disposition"]
