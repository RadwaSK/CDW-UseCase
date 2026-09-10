"""Phase 3 acceptance: approval policy, interrupt/resume, and ticket safety."""

import pytest

from app.db.models import ChangeTicket, TraceEvent
from app.graph.approval import evaluate_approval_policy
from app.graph.workflow import (
    get_pending_approval,
    is_awaiting_approval,
    resume_with_decision,
    run_assessment,
)
from app.models.findings import RiskFinding
from app.models.plan import ModernizationOption, ModernizationPlan, RoadmapPhase

PII_OBJECTIVE = "Prepare the order service for cloud deployment while protecting customer PII."


def _risk(severity="low", category="other") -> RiskFinding:
    from app.models.evidence import EvidenceReference

    return RiskFinding(
        category=category,
        title=f"{category} finding",
        description="d",
        severity=severity,
        recommended_action="a",
        policy_reference="security_standard.md",
        evidence=[
            EvidenceReference(
                file_path="f.py", chunk_id="c1", snippet="s", source="f.py",
                start_line=1, end_line=2,
            )
        ],
        confidence=0.9,
    )


def _plan(effort="medium", touches_auth=False) -> ModernizationPlan:
    return ModernizationPlan(
        summary="s",
        options=[
            ModernizationOption(
                name="opt", description="d", trade_offs="t", effort=effort, risk_reduction="r"
            )
        ],
        recommended_option="opt",
        recommendation_rationale="because",
        roadmap=[RoadmapPhase(phase="now", items=["x"])],
        estimated_effort=effort,
        touches_auth=touches_auth,
    )


# --- the policy itself, in isolation ---


def test_no_approval_needed_for_benign_assessment():
    assert evaluate_approval_policy("a1", [_risk("low")], _plan()) is None


@pytest.mark.parametrize(
    "risks,plan,trigger",
    [
        ([_risk("critical")], _plan(), "critical finding"),
        ([_risk("low", "pii")], _plan(), "PII exposure"),
        ([_risk("low", "secret")], _plan(), "hard-coded secret"),
        ([_risk("low")], _plan(touches_auth=True), "touches auth"),
        ([_risk("low")], _plan(effort="high"), "high effort"),
    ],
)
def test_each_policy_trigger_requires_approval(risks, plan, trigger):
    request = evaluate_approval_policy("a1", risks, plan)
    assert request is not None, f"{trigger} should require approval"
    assert request.reasons


def test_approval_request_states_it_only_permits_a_simulated_ticket():
    request = evaluate_approval_policy("a1", [_risk("critical")], _plan())
    assert "simulated" in request.proposed_action.lower()
    assert "no code or infrastructure is modified" in request.proposed_action.lower()


# --- end-to-end through the graph ---


def test_pii_secret_fixture_pauses_for_approval(ingested, assessment_record):
    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")

    assert is_awaiting_approval(assessment_record)
    request = get_pending_approval(assessment_record)
    assert request["reasons"]
    assert request["highest_severity"] == "critical"


def test_denial_creates_no_ticket(ingested, assessment_record, db_session):
    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")
    state = resume_with_decision(assessment_record, approved=False, comment="Not now.")

    assert state["status"] == "completed"
    assert state.get("ticket_record") is None
    assert (
        db_session.query(ChangeTicket).filter_by(assessment_id=assessment_record).count() == 0
    )
    assert state["final_report"].approval.approved is False
    assert state["final_report"].approval.ticket_number is None


def test_approval_creates_exactly_one_chg_demo_ticket(ingested, assessment_record, db_session):
    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")
    state = resume_with_decision(assessment_record, approved=True, comment="Approved.")

    tickets = db_session.query(ChangeTicket).filter_by(assessment_id=assessment_record).all()
    assert len(tickets) == 1
    assert tickets[0].ticket_number.startswith("CHG-DEMO-")
    assert state["ticket_record"]["ticket_number"] == tickets[0].ticket_number
    assert state["final_report"].approval.ticket_number == tickets[0].ticket_number


def test_resuming_a_completed_assessment_does_not_duplicate_the_ticket(
    ingested, assessment_record, db_session
):
    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")
    resume_with_decision(assessment_record, approved=True, comment="Approved.")

    # A second decision on a finished run must be refused outright.
    with pytest.raises(ValueError):
        resume_with_decision(assessment_record, approved=True, comment="Again.")

    assert (
        db_session.query(ChangeTicket).filter_by(assessment_id=assessment_record).count() == 1
    )


def test_ticket_tool_is_idempotent_if_called_twice_directly(
    ingested, assessment_record, db_session
):
    """Defense in depth: even a direct second tool call returns the same ticket."""
    from app.models.approval import TicketRequest
    from app.tools.servicenow import MockServiceNowChangeTool

    request = TicketRequest(
        assessment_id=assessment_record,
        sample_app_id="legacy_order_service",
        objective=PII_OBJECTIVE,
        summary="s",
        highest_severity="critical",
    )
    tool = MockServiceNowChangeTool(db_session)
    first = tool.create_assessment_ticket(request)
    second = tool.create_assessment_ticket(request)

    assert first.ticket_number == second.ticket_number
    assert second.was_existing is True
    assert (
        db_session.query(ChangeTicket).filter_by(assessment_id=assessment_record).count() == 1
    )


def test_ticket_node_refuses_without_approval(ingested, assessment_record):
    """The guard inside the node, independent of the routing edge."""
    from app.graph.nodes import ticket_node

    with pytest.raises(RuntimeError, match="without an explicit approval"):
        ticket_node({"assessment_id": assessment_record, "approval_decision": {"approved": False}})


# --- tracing ---


def test_trace_events_recorded_for_every_node(ingested, assessment_record, db_session):
    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")
    resume_with_decision(assessment_record, approved=True, comment="Approved.")

    events = db_session.query(TraceEvent).filter_by(assessment_id=assessment_record).all()
    nodes = {e.node for e in events}
    assert {"retrieve", "architecture", "security", "planner", "reviewer", "approval_gate",
            "ticket", "report"} <= nodes

    for e in events:
        assert e.trace_id
        assert e.event_type


def test_trace_payloads_contain_no_prompt_or_content(ingested, assessment_record, db_session):
    """Sanitization: only counts/names/timings are persisted."""
    from app.services.tracing import ALLOWED_PAYLOAD_KEYS

    run_assessment(assessment_record, PII_OBJECTIVE, "legacy_order_service")

    events = db_session.query(TraceEvent).filter_by(assessment_id=assessment_record).all()
    assert events
    for e in events:
        assert set(e.payload).issubset(ALLOWED_PAYLOAD_KEYS)
        assert "snippet" not in e.payload
        assert "content" not in e.payload
