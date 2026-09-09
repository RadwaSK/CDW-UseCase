from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_status_even_without_database():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unavailable"}


def test_health_available_under_api_v1_prefix():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
