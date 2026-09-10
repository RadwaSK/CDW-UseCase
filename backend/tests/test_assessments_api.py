from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

OBJECTIVE = "Prepare the order service for cloud deployment while protecting customer PII."


def _create() -> dict:
    response = client.post(
        "/api/v1/assessments",
        json={"sample_app_id": "legacy_order_service", "objective": OBJECTIVE},
    )
    assert response.status_code == 201
    return response.json()


def _approve(assessment_id: str, approved: bool = True) -> dict:
    response = client.post(
        f"/api/v1/assessments/{assessment_id}/approval",
        json={"approved": approved, "comment": "via API test"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_assessment_pauses_for_approval(ingested):
    body = _create()

    assert body["sample_app_id"] == "legacy_order_service"
    assert body["status"] == "awaiting_approval"
    assert body["pending_approval"]["reasons"]
    assert body["pending_approval"]["highest_severity"] == "critical"


def test_approving_completes_and_returns_report_with_ticket(ingested):
    created = _create()
    body = _approve(created["id"])

    assert body["status"] == "completed"
    report = body["report"]
    assert report["executive_summary"]
    assert report["risk_register"]
    assert report["approval"]["approved"] is True
    assert report["approval"]["ticket_number"].startswith("CHG-DEMO-")


def test_denying_completes_with_no_ticket(ingested):
    created = _create()
    body = _approve(created["id"], approved=False)

    assert body["status"] == "completed"
    assert body["report"]["approval"]["approved"] is False
    assert body["report"]["approval"]["ticket_number"] is None


def test_approving_twice_is_rejected(ingested):
    created = _create()
    _approve(created["id"])

    second = client.post(
        f"/api/v1/assessments/{created['id']}/approval",
        json={"approved": True, "comment": "again"},
    )
    assert second.status_code == 409


def test_approval_on_unknown_assessment_returns_404():
    response = client.post(
        "/api/v1/assessments/8f14e45f-ceea-467a-9f39-1b1f1b1f1b1f/approval",
        json={"approved": True, "comment": ""},
    )
    assert response.status_code == 404


def test_get_assessment_returns_stored_report(ingested):
    created = _create()
    approved = _approve(created["id"])

    fetched = client.get(f"/api/v1/assessments/{created['id']}")
    assert fetched.status_code == 200
    assert (
        fetched.json()["report"]["executive_summary"]
        == approved["report"]["executive_summary"]
    )


def test_get_report_endpoint(ingested):
    created = _create()
    _approve(created["id"])

    report = client.get(f"/api/v1/assessments/{created['id']}/report")
    assert report.status_code == 200
    assert report.json()["scope"]["sample_app_id"] == "legacy_order_service"


def test_trace_endpoint_returns_sanitized_events(ingested):
    created = _create()
    _approve(created["id"])

    trace = client.get(f"/api/v1/assessments/{created['id']}/trace")
    assert trace.status_code == 200
    events = trace.json()
    assert events

    nodes = {e["node"] for e in events}
    assert {"retrieve", "architecture", "security", "planner", "reviewer", "report"} <= nodes
    for e in events:
        assert e["event_type"]
        assert "snippet" not in e["payload"]
        assert "prompt" not in e["payload"]


def test_checkpointed_state_endpoint(ingested):
    created = _create()
    _approve(created["id"])

    state = client.get(f"/api/v1/assessments/{created['id']}/state")
    assert state.status_code == 200
    body = state.json()
    assert body["status"] == "completed"
    assert body["awaiting_approval"] is False
    assert body["evidence_count"] > 0
    assert body["risk_finding_count"] > 0


def test_get_unknown_assessment_returns_404():
    response = client.get("/api/v1/assessments/8f14e45f-ceea-467a-9f39-1b1f1b1f1b1f")
    assert response.status_code == 404


def test_create_assessment_rejects_unknown_sample_app():
    response = client.post(
        "/api/v1/assessments",
        json={"sample_app_id": "not_a_real_app", "objective": "Do something."},
    )
    assert response.status_code == 422


def test_create_assessment_rejects_empty_objective():
    response = client.post(
        "/api/v1/assessments",
        json={"sample_app_id": "legacy_order_service", "objective": ""},
    )
    assert response.status_code == 422
