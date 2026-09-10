"""Execute golden cases against the real graph and score the outcomes.

Nothing here is mocked except the models themselves (fake embeddings + rule-based
agents, forced by app.evaluation.run). The graph, retrieval, reviewer, approval
policy, and ticket tool are the same code paths the API uses, so a passing
evaluation is evidence about the shipped system rather than about a stub.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import delete, select, text

from app.db.models import Assessment, ChangeTicket
from app.db.session import SessionLocal
from app.evaluation.dataset import EvalCase
from app.graph.workflow import (
    get_assessment_state,
    is_awaiting_approval,
    resume_with_decision,
    run_assessment,
)
from app.models.report import AssessmentReport

# What to do with the approval gate on a given run.
DECISION_LEAVE_PENDING = None  # never resume: the "approval missing" arm
DECISION_DENY = False
DECISION_APPROVE = True

_STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "including", "into", "is",
    "level", "of", "on", "or", "should", "the", "to", "with",
}


@dataclass
class RunOutcome:
    """One execution of one case, at one approval decision."""

    assessment_id: str
    decision: bool | None
    paused: bool
    ticket_count: int
    report: AssessmentReport | None = None
    evidence_chunk_ids: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    case: EvalCase
    runs: list[RunOutcome]
    checks: dict[str, bool]
    evidence_coverage: float
    key_findings_matched: float
    observed_risk_level: str | None
    observed_approval_required: bool
    removed_claim_count: int
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())

    @property
    def primary(self) -> RunOutcome:
        """The run that produced the report we score: approved, else the only one."""
        for run in self.runs:
            if run.decision is DECISION_APPROVE:
                return run
        return self.runs[-1]


def _execute(case: EvalCase, decision: bool | None) -> RunOutcome:
    """Create a real assessment row and drive the graph exactly as the API does."""
    with SessionLocal() as db:
        row = Assessment(
            sample_app_id=case.sample_app_id, objective=case.objective, status="pending"
        )
        db.add(row)
        db.commit()
        assessment_id = row.id

    # A node that raises is a failed case, not a failed evaluation: the harness
    # records it and carries on, so one broken case still yields a full report.
    failures: list[str] = []
    try:
        run_assessment(assessment_id, case.objective, case.sample_app_id)
        paused = is_awaiting_approval(assessment_id)
        if paused and decision is not None:
            resume_with_decision(assessment_id, decision, comment=f"eval:{case.case_id}")
    except Exception as exc:  # noqa: BLE001 - surfaced as a case failure below
        paused = is_awaiting_approval(assessment_id)
        failures.append(f"{type(exc).__name__}: {exc}".splitlines()[0])

    state = get_assessment_state(assessment_id) or {}
    with SessionLocal() as db:
        ticket_count = len(
            db.scalars(
                select(ChangeTicket).where(ChangeTicket.assessment_id == assessment_id)
            ).all()
        )

    return RunOutcome(
        assessment_id=assessment_id,
        decision=decision,
        paused=paused,
        ticket_count=ticket_count,
        report=state.get("final_report"),
        evidence_chunk_ids={e.evidence.chunk_id for e in state.get("retrieved_evidence", [])},
        errors=[*state.get("errors", []), *failures],
    )


def _evidence_counts(report: AssessmentReport | None, valid_ids: set[str]) -> tuple[int, int]:
    """(findings whose every citation resolves to a real chunk, total findings).

    Recomputed from the retrieved evidence rather than trusting the reviewer's own
    verdict — the point is to check that the reviewer actually did its job. Counts
    rather than a ratio, so the pass/fail check is an integer comparison.
    """
    if report is None:
        return 0, 0
    findings = [*report.architecture_findings, *report.risk_findings]
    supported = sum(
        1
        for f in findings
        if f.evidence and all(r.chunk_id in valid_ids for r in f.evidence)
    )
    return supported, len(findings)


def _tool_safety(runs: list[RunOutcome]) -> tuple[bool, list[str]]:
    """A ticket may exist only on an arm that was both paused and explicitly approved."""
    notes: list[str] = []
    for run in runs:
        expected = 1 if run.decision is DECISION_APPROVE and run.paused else 0
        if run.ticket_count != expected:
            notes.append(
                f"decision={run.decision!r}: {run.ticket_count} ticket(s), expected {expected}"
            )
    return not notes, notes


def _content_words(phrase: str) -> set[str]:
    return {w for w in re.findall(r"[a-z_]+", phrase.lower()) if w not in _STOPWORDS and len(w) > 2}


def _key_findings_matched(report: AssessmentReport | None, expected: list[str]) -> float:
    """Informational only: fuzzy overlap between expected phrasing and the report.

    Deliberately not a pass/fail gate — the expected strings are prose, and
    scoring prose similarity with a keyword heuristic would make the gate a
    measure of wording rather than of behavior.
    """
    if not expected:
        return 1.0
    if report is None:
        return 0.0

    haystacks = [
        f"{f.title} {f.description}".lower()
        for f in [*report.architecture_findings, *report.risk_findings]
    ]
    haystacks.extend(f"{c.claim} {c.reason}".lower() for c in report.removed_claims)
    haystacks.append(report.executive_summary.lower())

    matched = 0
    for phrase in expected:
        words = _content_words(phrase)
        if not words:
            continue
        if any(len(words & _content_words(h)) / len(words) >= 0.5 for h in haystacks):
            matched += 1
    return matched / len(expected)


def _run_arms(case: EvalCase) -> list[RunOutcome]:
    """Every approval arm the case's expectation implies.

    A case that should pause is run three times, because "no ticket without
    approval" has to hold when the decision is missing as well as when it is an
    explicit denial — one arm each, plus the approval that should produce exactly one.
    """
    if not case.expected_approval_required:
        return [_execute(case, DECISION_LEAVE_PENDING)]
    return [
        _execute(case, DECISION_LEAVE_PENDING),
        _execute(case, DECISION_DENY),
        _execute(case, DECISION_APPROVE),
    ]


def evaluate_case(case: EvalCase) -> CaseResult:
    """Run a case through every approval arm its expectation implies, then score it."""
    notes: list[str] = []
    runs = _run_arms(case)

    observed_approval_required = runs[0].paused
    primary = next((r for r in runs if r.decision is DECISION_APPROVE), runs[-1])
    report = primary.report

    supported, total_findings = _evidence_counts(report, primary.evidence_chunk_ids)
    if report is None:
        coverage, fully_grounded = 0.0, False
        notes.append("no final report produced, so report-derived checks cannot pass")
    else:
        coverage = 1.0 if total_findings == 0 else supported / total_findings
        fully_grounded = supported == total_findings

    key_matched = _key_findings_matched(report, case.expected_key_findings)
    removed = len(report.removed_claims) if report else 0

    tool_safety, safety_notes = _tool_safety(runs)
    notes.extend(safety_notes)

    observed_categories = {f.category for f in report.risk_findings} if report else set()
    missing_categories = sorted(set(case.expected_finding_categories) - observed_categories)
    if missing_categories:
        notes.append(
            f"expected risk categories not found: {', '.join(missing_categories)} "
            f"(observed: {', '.join(sorted(observed_categories)) or 'none'})"
        )

    checks = {
        "approval_policy": observed_approval_required == case.expected_approval_required,
        "risk_level": report is not None
        and report.overall_risk_level == case.expected_risk_level,
        "finding_categories": not missing_categories,
        "evidence_coverage": fully_grounded,
        "tool_safety": tool_safety,
        "no_errors": not any(r.errors for r in runs),
    }
    if case.expected_removed_claims is not None:
        checks["removed_claims"] = (removed > 0) == case.expected_removed_claims

    for run in runs:
        notes.extend(f"run error: {e}" for e in run.errors)

    return CaseResult(
        case=case,
        runs=runs,
        checks=checks,
        evidence_coverage=coverage,
        key_findings_matched=key_matched,
        observed_risk_level=report.overall_risk_level if report else None,
        observed_approval_required=observed_approval_required,
        removed_claim_count=removed,
        notes=notes,
    )


def cleanup(results: list[CaseResult]) -> int:
    """Delete the rows and checkpoints this evaluation created.

    Assessments cascade to tickets and trace events; LangGraph's checkpoint tables
    have no foreign key to them, so those are removed by thread id explicitly.
    """
    ids = [run.assessment_id for r in results for run in r.runs]
    if not ids:
        return 0
    with SessionLocal() as db:
        db.execute(delete(Assessment).where(Assessment.id.in_(ids)))
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            db.execute(
                text(f"DELETE FROM {table} WHERE thread_id = ANY(:ids)"),
                {"ids": ids},
            )
        db.commit()
    return len(ids)
