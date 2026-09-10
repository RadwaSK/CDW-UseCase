"""The agent call must run inside traced_node: otherwise durations exclude the
slowest step and a model failure escapes before node_failed is written. These
tests pin both, and fail against the pre-fix structure."""

import json
import time

import pytest

from app.db.models import TraceEvent
from app.graph import fake_agents
from app.graph.workflow import is_awaiting_approval, resume_with_decision, run_assessment
from app.services.tracing import ALLOWED_PAYLOAD_KEYS

OBJECTIVE = "Assess the order service for PII handling issues before a data migration."

GRAPH_NODES = {
    "retrieve",
    "architecture",
    "security",
    "planner",
    "reviewer",
    "approval_gate",
    "ticket",
    "report",
}

# Stands in for prompt/model-output text; must not appear in any persisted column.
CANARY = "PROMPT-CANARY-do-not-persist-9f3a"


def _events(db_session, assessment_id) -> list[TraceEvent]:
    return db_session.query(TraceEvent).filter_by(assessment_id=assessment_id).all()


def test_completed_assessment_records_a_completion_for_every_node(
    ingested, assessment_record, db_session
):
    run_assessment(assessment_record, OBJECTIVE, "legacy_order_service")
    assert is_awaiting_approval(assessment_record)
    resume_with_decision(assessment_record, approved=True, comment="Approved.")

    events = _events(db_session, assessment_record)
    completed = {e.node for e in events if e.event_type == "node_completed"}
    assert completed >= GRAPH_NODES, f"missing completions: {GRAPH_NODES - completed}"

    for event in events:
        assert event.trace_id
        assert event.duration_ms is None or event.duration_ms >= 0
        assert event.error_class is None


@pytest.mark.parametrize(
    ("agent_attr", "node"),
    [
        ("fake_architecture_findings", "architecture"),
        ("fake_risk_findings", "security"),
        ("fake_plan", "planner"),
    ],
)
def test_agent_failure_persists_a_sanitized_node_failed_event(
    ingested, assessment_record, db_session, monkeypatch, agent_attr, node
):
    """A failure inside the agent call must still leave a trace behind."""

    def boom(*_args, **_kwargs):
        raise RuntimeError(f"upstream model rejected the request: {CANARY}")

    monkeypatch.setattr(fake_agents, agent_attr, boom)

    with pytest.raises(Exception, match="upstream model rejected"):
        run_assessment(assessment_record, OBJECTIVE, "legacy_order_service")

    failures = [
        e for e in _events(db_session, assessment_record)
        if e.event_type == "node_failed" and e.node == node
    ]
    assert failures, f"no node_failed event persisted for {node!r}"

    event = failures[0]
    assert event.error_class == "RuntimeError"
    assert event.duration_ms is not None
    # Only the exception's type is recorded, never its message.
    assert CANARY not in json.dumps(event.payload)
    assert CANARY not in (event.error_class or "")
    assert set(event.payload).issubset(ALLOWED_PAYLOAD_KEYS)


def test_failed_agent_trace_still_names_the_attempted_model(
    ingested, assessment_record, db_session, monkeypatch
):
    """`model` is set before the call, so a failure still says what was attempted."""

    def boom(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(fake_agents, "fake_risk_findings", boom)

    with pytest.raises(Exception, match="model unavailable"):
        run_assessment(assessment_record, OBJECTIVE, "legacy_order_service")

    failure = next(
        e for e in _events(db_session, assessment_record)
        if e.event_type == "node_failed" and e.node == "security"
    )
    assert failure.payload.get("model") == "deterministic-fake"


def test_node_duration_covers_the_agent_call(
    ingested, assessment_record, db_session, monkeypatch
):
    """The regression guard: with the call outside the trace, this read ~0ms."""
    delay_s = 0.05
    real_agent = fake_agents.fake_risk_findings

    def slow_agent(*args, **kwargs):
        time.sleep(delay_s)
        return real_agent(*args, **kwargs)

    monkeypatch.setattr(fake_agents, "fake_risk_findings", slow_agent)

    run_assessment(assessment_record, OBJECTIVE, "legacy_order_service")

    security = next(
        e for e in _events(db_session, assessment_record)
        if e.node == "security" and e.event_type == "node_completed"
    )
    assert security.duration_ms >= delay_s * 1000
