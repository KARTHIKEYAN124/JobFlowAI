import json
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


def test_preferences_persist_and_operational_pages_use_database_values():
    with TestClient(app) as client:
        email = f"preferences-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Preference Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        saved = client.put(
            "/api/v1/settings",
            headers=headers,
            json={
                "high_match_email": False,
                "daily_digest": True,
                "followup_reminders": False,
                "interview_preparation": True,
                "notification_email": email,
                "telegram_chat_id": "12345",
            },
        )
        assert saved.status_code == 200
        assert client.get("/api/v1/settings", headers=headers).json()["high_match_email"] is False
        assert client.get("/api/v1/automations", headers=headers).json()["executions_today"] >= 0
        assert len(client.get("/api/v1/automations", headers=headers).json()["workflows"]) == 10
        overview = client.get("/api/v1/analytics/overview", headers=headers)
        assert overview.status_code == 200
        assert len(overview.json()["weekly_jobs"]) == 12


def test_admin_workflow_runs_enforces_role():
    with TestClient(app) as client:
        email = f"rbac-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "RBAC Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        assert client.get("/api/v1/admin/workflow-runs", headers=headers).status_code == 403


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


def test_portal_session_requires_review_and_records_confirmed_submission(monkeypatch):
    external_id = f"ashby:portal:{uuid.uuid4().hex}"

    async def fake_portal_job(_):
        return {
            "external_id": external_id,
            "title": "Python Engineer",
            "company_name": "Acme",
            "location": "Remote",
            "description_text": "Build Python and FastAPI services for production systems.",
            "application_url": "https://jobs.ashbyhq.com/acme/test",
            "source": "Ashby public Job Board API",
            "posted_at": "2026-08-25T10:00:00Z",
        }

    monkeypatch.setattr(routes, "fetch_portal_job", fake_portal_job)
    with TestClient(app) as client:
        email = f"portal-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Portal Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        job = client.post(
            "/api/v1/jobs/import-url", headers=headers, json={"url": "https://jobs.ashbyhq.com/acme/test"}
        ).json()
        application = client.post(
            "/api/v1/applications",
            headers=headers,
            json={
                "job_id": job["id"],
                "notes": json.dumps(
                    {"email": email, "phone": "123", "truth_confirmation": "on", "review_confirmation": "on"}
                ),
            },
        )
        app_id = application.json()["id"]
        assert (
            client.post(f"/api/v1/applications/{app_id}/portal-session", headers=headers).status_code == 409
        )
        prepared = client.post("/api/v1/ai/application", headers=headers, json={"application_id": app_id})
        assert prepared.status_code == 200
        launched = client.post(f"/api/v1/applications/{app_id}/portal-session", headers=headers)
        assert launched.status_code == 201
        token = launched.json()["portal_url"].split("#jobflow=", 1)[1]
        package = client.get(f"/api/v1/portal-sessions/{token}")
        assert package.status_code == 200
        assert package.json()["candidate"]["email"] == email
        submitted = client.post(f"/api/v1/portal-sessions/{token}/submitted")
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "APPLIED"


def test_dashboard_uses_current_user_application_data():
    with TestClient(app) as client:
        email = f"dashboard-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Dashboard Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        before = client.get("/api/v1/analytics/dashboard", headers=headers)
        assert before.status_code == 200
        assert before.json()["applications"] == 0
        job_id = client.get("/api/v1/jobs?include_demo=true", headers=headers).json()[0]["id"]
        created = client.post("/api/v1/applications", headers=headers, json={"job_id": job_id})
        assert created.status_code == 201
        after = client.get("/api/v1/analytics/dashboard", headers=headers).json()
        assert after["applications"] == 1
        assert after["pipeline"]["PREPARING"] == 1
        assert after["recent_applications"][0]["job_id"] == job_id


def test_demo_jobs_are_hidden_and_cannot_launch_a_portal():
    with TestClient(app) as client:
        email = f"demo-guard-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Demo Guard"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        assert all(
            job["source"] != "JobFlow demo" for job in client.get("/api/v1/jobs", headers=headers).json()
        )
        demo = next(
            job
            for job in client.get("/api/v1/jobs?include_demo=true", headers=headers).json()
            if job["source"] == "JobFlow demo"
        )
        application = client.post("/api/v1/applications", headers=headers, json={"job_id": demo["id"]}).json()
        client.post("/api/v1/ai/application", headers=headers, json={"application_id": application["id"]})
        launched = client.post(f"/api/v1/applications/{application['id']}/portal-session", headers=headers)
        assert launched.status_code == 409
        assert "demo listing" in launched.json()["detail"].lower()


def test_application_answers_are_saved_and_reused():
    with TestClient(app) as client:
        email = f"saved-answers-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Saved Answers"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        demo = client.get("/api/v1/jobs?include_demo=true", headers=headers).json()[0]
        notes = json.dumps(
            {
                "phone": "+49 123",
                "work_authorization": "Yes",
                "save_for_future": "on",
                "_question_labels": json.dumps({"work_authorization": "Authorized to work?"}),
            }
        )
        created = client.post(
            "/api/v1/applications", headers=headers, json={"job_id": demo["id"], "notes": notes}
        )
        assert created.status_code == 201
        saved = client.get("/api/v1/application-answers", headers=headers).json()
        assert saved["answers"]["phone"] == "+49 123"
        assert saved["answers"]["work_authorization"] == "Yes"
        assert saved["questions"]["work_authorization"] == "Authorized to work?"


def test_real_portal_questions_are_returned_without_invention(monkeypatch):
    external_id = f"ashby:questions:{uuid.uuid4().hex}"

    async def fake_portal_job(_):
        return {
            "external_id": external_id,
            "title": "Python Engineer",
            "company_name": "Acme",
            "location": "Remote",
            "description_text": "Build Python and FastAPI services for production systems.",
            "application_url": "https://jobs.ashbyhq.com/acme/test",
            "source": "Ashby public Job Board API",
            "posted_at": "2026-08-25T10:00:00Z",
        }

    async def fake_questions(_):
        return {
            "questions": [
                {
                    "key": "eligible",
                    "label": "Are you eligible?",
                    "required": True,
                    "type": "input_text",
                    "options": [],
                }
            ],
            "source": "ATS schema",
            "note": "Current employer form",
        }

    monkeypatch.setattr(routes, "fetch_portal_job", fake_portal_job)
    monkeypatch.setattr(routes, "fetch_application_questions", fake_questions)
    with TestClient(app) as client:
        email = f"questions-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Question Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        real_job = client.post(
            "/api/v1/jobs/import-url", headers=headers, json={"url": "https://jobs.ashbyhq.com/acme/test"}
        ).json()
        result = client.get(f"/api/v1/jobs/{real_job['id']}/application-questions", headers=headers)
        assert result.status_code == 200
        assert result.json()["questions"] == [
            {
                "key": "eligible",
                "label": "Are you eligible?",
                "required": True,
                "type": "input_text",
                "options": [],
            }
        ]


def test_existing_portal_job_is_matched_for_each_user(monkeypatch):
    external_id = f"ashby:test:{uuid.uuid4().hex}"

    async def fake_portal_job(_):
        return {
            "external_id": external_id,
            "title": "Python Engineer",
            "company_name": "Acme",
            "location": "Remote",
            "description_text": "Build Python and FastAPI services for production systems.",
            "application_url": "https://jobs.ashbyhq.com/acme/test",
            "source": "Ashby public Job Board API",
            "posted_at": "2026-08-25T10:00:00Z",
        }

    monkeypatch.setattr(routes, "fetch_portal_job", fake_portal_job)
    with TestClient(app) as client:
        for index in range(2):
            email = f"existing-job-{index}-{uuid.uuid4().hex}@example.com"
            registration = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "verification-password", "full_name": "Match Test"},
            )
            headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
            imported = client.post(
                "/api/v1/jobs/import-url", headers=headers, json={"url": "https://jobs.ashbyhq.com/acme/test"}
            )
            assert imported.status_code == 201
            matches = client.get("/api/v1/matches", headers=headers).json()
            assert any(match["job_id"] == imported.json()["id"] for match in matches)


def test_greenhouse_existing_application_uses_canonical_portal_url(monkeypatch):
    external_id = f"greenhouse:acme:{uuid.uuid4().hex}"

    async def fake_portal_job(_):
        return {
            "external_id": external_id,
            "title": "Python Engineer",
            "company_name": "Acme",
            "location": "Remote",
            "description_text": "Build Python and FastAPI services for production systems.",
            "application_url": "https://careers.example.com/redirected",
            "source": "Greenhouse public Job Board API",
            "posted_at": "2026-08-25T10:00:00Z",
        }

    monkeypatch.setattr(routes, "fetch_portal_job", fake_portal_job)
    with TestClient(app) as client:
        email = f"greenhouse-existing-{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "verification-password", "full_name": "Portal Test"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        job = client.post(
            "/api/v1/jobs/import-url",
            headers=headers,
            json={"url": "https://job-boards.greenhouse.io/acme/jobs/123"},
        ).json()
        application = client.post("/api/v1/applications", headers=headers, json={"job_id": job["id"]}).json()
        client.post("/api/v1/ai/application", headers=headers, json={"application_id": application["id"]})
        launched = client.post(
            f"/api/v1/applications/{application['id']}/portal-session", headers=headers
        ).json()
        assert launched["portal_url"].startswith(
            f"https://job-boards.greenhouse.io/acme/jobs/{external_id.rsplit(':', 1)[1]}#jobflow="
        )
