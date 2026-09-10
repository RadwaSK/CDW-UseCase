from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_sample_apps():
    response = client.get("/api/v1/sample-apps")
    assert response.status_code == 200
    apps = response.json()
    assert any(a["id"] == "legacy_order_service" for a in apps)
    for a in apps:
        assert a["name"]
        assert a["description"]
