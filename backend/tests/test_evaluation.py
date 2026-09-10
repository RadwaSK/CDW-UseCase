"""The evaluation is a quality gate, so it needs its own tests.

A gate that cannot fail is worthless: several of these deliberately feed the
scorers bad input and assert that they say so.
"""

import json

import pytest

from app.evaluation.dataset import EvalCase, load_cases
from app.evaluation.harness import (
    DECISION_APPROVE,
    DECISION_DENY,
    RunOutcome,
    _evidence_counts,
    _tool_safety,
    evaluate_case,
)
from app.models.evidence import EvidenceReference
from app.models.findings import RiskFinding
from app.models.report import AssessmentReport, ScopeSummary


def _ref(chunk_id: str) -> EvidenceReference:
    return EvidenceReference(
        file_path="legacy_order_service/config.py",
        chunk_id=chunk_id,
        snippet="API_KEY = 'literal'",
        source="config.py",
        start_line=1,
        end_line=2,
    )


def _report_with(chunk_ids: list[str]) -> AssessmentReport:
    return AssessmentReport(
        executive_summary="summary",
        scope=ScopeSummary(
            sample_app_id="legacy_order_service",
            objective="obj",
            files_reviewed=["legacy_order_service/config.py"],
            evidence_count=len(chunk_ids),
        ),
        architecture_summary="arch",
        risk_findings=[
            RiskFinding(
                category="secret",
                title=f"finding-{cid}",
                description="d",
                severity="critical",
                recommended_action="a",
                policy_reference="security_standard.md",
                evidence=[_ref(cid)],
                confidence=0.9,
            )
            for cid in chunk_ids
        ],
    )


def test_shipped_dataset_loads_and_every_case_is_valid():
    cases = load_cases()
    assert cases
    assert all(isinstance(c, EvalCase) for c in cases)
    # Both demo paths must stay represented, or the gate stops covering one.
    assert any(c.expected_approval_required for c in cases)
    assert any(not c.expected_approval_required for c in cases)


def test_duplicate_case_ids_are_rejected(tmp_path):
    case = {
        "case_id": "dupe",
        "sample_app_id": "legacy_order_service",
        "objective": "o",
        "scenario_type": "pii",
        "expected_risk_level": "critical",
        "expected_approval_required": True,
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case) + "\n" + json.dumps(case) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate case_id"):
        load_cases(path)


def test_malformed_case_names_its_line(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"case_id": "missing-everything-else"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"cases\.jsonl:1"):
        load_cases(path)


def test_evidence_counts_flags_a_dangling_citation():
    report = _report_with(["chunk-a", "chunk-missing"])
    supported, total = _evidence_counts(report, valid_ids={"chunk-a"})
    assert (supported, total) == (1, 2)


def test_evidence_counts_accepts_fully_grounded_findings():
    report = _report_with(["chunk-a", "chunk-b"])
    assert _evidence_counts(report, valid_ids={"chunk-a", "chunk-b"}) == (2, 2)


def _outcome(decision, paused, tickets) -> RunOutcome:
    return RunOutcome(
        assessment_id="00000000-0000-0000-0000-000000000000",
        decision=decision,
        paused=paused,
        ticket_count=tickets,
    )


def test_tool_safety_rejects_a_ticket_created_without_approval():
    safe, notes = _tool_safety([_outcome(DECISION_DENY, paused=True, tickets=1)])
    assert not safe
    assert "expected 0" in notes[0]


def test_tool_safety_rejects_a_missing_ticket_after_approval():
    safe, _ = _tool_safety([_outcome(DECISION_APPROVE, paused=True, tickets=0)])
    assert not safe


def test_tool_safety_accepts_the_correct_pattern():
    safe, notes = _tool_safety(
        [
            _outcome(None, paused=True, tickets=0),
            _outcome(DECISION_DENY, paused=True, tickets=0),
            _outcome(DECISION_APPROVE, paused=True, tickets=1),
        ]
    )
    assert safe
    assert notes == []


def test_wrong_expectation_makes_a_case_fail(ingested):
    """Proves the gate discriminates: the code is fine, the expectation is not."""
    case = EvalCase(
        case_id="deliberately-wrong",
        sample_app_id="legacy_order_service",
        objective="Assess the order service for PII handling issues.",
        scenario_type="pii",
        expected_risk_level="low",  # the legacy app is demonstrably not low risk
        expected_approval_required=False,
    )
    result = evaluate_case(case)
    assert not result.passed
    assert not result.checks["approval_policy"]


def test_every_golden_case_passes(ingested):
    """The gate itself: the shipped dataset must describe actual behavior."""
    failures = {}
    for case in load_cases():
        result = evaluate_case(case)
        if not result.passed:
            failures[case.case_id] = {
                "failed": [k for k, ok in result.checks.items() if not ok],
                "notes": result.notes,
            }
    assert not failures, f"golden cases failed: {json.dumps(failures, indent=2)}"
