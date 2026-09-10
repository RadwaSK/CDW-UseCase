"""Graph behaviour: analysis, evidence discipline, revision loop, checkpointing.

Every objective against this sample app surfaces critical PII/secret findings,
so runs pause at the approval gate; tests that need a finished report resume
with a decision. Approval-policy specifics live in test_approval.py.
"""

import pytest

from app.graph.workflow import (
    get_assessment_state,
    is_awaiting_approval,
    resume_with_decision,
    run_assessment,
)
from app.models.report import AssessmentReport

CLOUD_OBJECTIVE = (
    "Prepare the order service for cloud deployment while protecting customer PII."
)
REWRITE_OBJECTIVE = (
    "Evaluate whether the order service should be fully rewritten in a new language."
)


def _run_to_completion(assessment_id: str, objective: str, approved: bool = True):
    """Run, and if it pauses for approval, supply a decision so it finishes."""
    state = run_assessment(assessment_id, objective, "legacy_order_service")
    if is_awaiting_approval(assessment_id):
        state = resume_with_decision(assessment_id, approved=approved, comment="test")
    return state


@pytest.fixture
def cloud_run(ingested, assessment_record):
    return _run_to_completion(assessment_record, CLOUD_OBJECTIVE)


def test_assessment_completes_with_report(cloud_run):
    assert cloud_run["status"] == "completed"
    report = cloud_run["final_report"]
    assert isinstance(report, AssessmentReport)
    assert report.executive_summary
    assert report.scope.evidence_count > 0
    assert report.scope.files_reviewed
    assert report.limitations


def test_both_analysts_contributed(cloud_run):
    assert cloud_run["architecture_findings"], "architecture analyst produced nothing"
    assert cloud_run["risk_findings"], "security analyst produced nothing"


def test_every_finding_cites_retrieved_evidence(cloud_run):
    valid_ids = {e.evidence.chunk_id for e in cloud_run["retrieved_evidence"]}
    findings = cloud_run["architecture_findings"] + cloud_run["risk_findings"]
    assert findings
    for f in findings:
        assert f.evidence, f"{f.title} has no evidence"
        for ref in f.evidence:
            assert ref.chunk_id in valid_ids
            assert ref.snippet.strip()


def test_planted_security_issues_are_detected(cloud_run):
    categories = {f.category for f in cloud_run["risk_findings"]}
    assert "secret" in categories, "hard-coded key fixture not detected"
    assert "pii" in categories, "PII logging fixture not detected"


def test_risk_register_is_severity_ordered(cloud_run):
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    severities = [order[e.severity] for e in cloud_run["final_report"].risk_register]
    assert severities == sorted(severities, reverse=True)


def test_plan_recommends_an_offered_option(cloud_run):
    plan = cloud_run["final_report"].plan
    assert plan is not None
    assert plan.recommended_option in {o.name for o in plan.options}
    assert plan.roadmap


def test_service_context_from_asset_inventory_tool(cloud_run):
    context = cloud_run["service_context"]
    assert context["service_name"]
    assert context["data_classification"] == "contains-pii"


def test_state_is_checkpointed_and_retrievable(ingested, assessment_record):
    _run_to_completion(assessment_record, CLOUD_OBJECTIVE)

    restored = get_assessment_state(assessment_record)

    assert restored is not None
    assert restored["assessment_id"] == assessment_record
    assert restored["status"] == "completed"
    assert restored["final_report"] is not None


def test_unsupported_claim_is_removed_by_reviewer(ingested, assessment_record):
    """The weak-evidence scenario: a rewrite claim cites a chunk that isn't real."""
    state = _run_to_completion(assessment_record, REWRITE_OBJECTIVE)

    decision = state["review_decision"]
    assert decision.removed_claims, "reviewer accepted an unsupported claim"

    plan = state["final_report"].plan
    # The unsupported option must be gone entirely, not merely have its citation
    # stripped — otherwise the reader still sees a recommendation nothing backs.
    assert "Full rewrite in a new language" not in {o.name for o in plan.options}
    assert any("Full rewrite" in c.claim for c in decision.removed_claims)

    # No dangling citation survives anywhere in the plan.
    valid_ids = {e.evidence.chunk_id for e in state["retrieved_evidence"]}
    for ref in plan.evidence:
        assert ref.chunk_id in valid_ids
    for option in plan.options:
        for ref in option.evidence:
            assert ref.chunk_id in valid_ids

    # A surviving recommendation still has to be one of the offered options.
    assert plan.recommended_option in {o.name for o in plan.options}

    # ...and the report must disclose it rather than quietly dropping it.
    assert state["final_report"].removed_claims
    assert any("evidence" in limitation.lower() for limitation in state["final_report"].limitations)


def test_revision_loop_is_bounded(ingested, assessment_record):
    state = _run_to_completion(assessment_record, REWRITE_OBJECTIVE)
    assert state["revision_count"] <= state["max_revisions"]
