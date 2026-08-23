from fastapi.testclient import TestClient

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
