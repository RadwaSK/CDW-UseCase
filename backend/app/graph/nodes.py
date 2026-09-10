"""LangGraph node implementations. Each analyst/planner node picks the rule-based
or the live-model path from settings.use_fake_llm; the state contract is identical."""

import logging

from langgraph.types import interrupt
from pydantic import BaseModel

from app.core.config import settings
from app.core.model_factory import structured_completion
from app.db.session import SessionLocal
from app.graph import fake_agents
from app.graph.approval import evaluate_approval_policy
from app.graph.reviewer import review
from app.graph.state import AssessmentState
from app.models.approval import ApprovalDecision, TicketRequest
from app.models.evidence import RetrievedEvidence
from app.models.findings import ArchitectureFinding, RiskFinding
from app.models.plan import ModernizationPlan
from app.models.report import (
    ApprovalRecord,
    AssessmentReport,
    RiskRegisterEntry,
    ScopeSummary,
)
from app.prompts import agents as prompts
from app.services.tracing import traced_node
from app.tools.asset_inventory import MockAssetInventoryTool
from app.tools.repository_evidence import RepositoryEvidenceTool
from app.tools.servicenow import MockServiceNowChangeTool

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _dedupe_evidence(items: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
    seen, out = set(), []
    for item in items:
        if item.evidence.chunk_id not in seen:
            seen.add(item.evidence.chunk_id)
            out.append(item)
    return out


def retrieve_evidence_node(state: AssessmentState) -> dict:
    """Pull app + standards evidence with per-agent queries, deduped into one set."""
    objective = state["objective"]
    sample_app_id = state["sample_app_id"]

    with traced_node(state, "retrieve") as metrics:
        with SessionLocal() as db:
            tool = RepositoryEvidenceTool(db)
            correlation_id = state.get("assessment_id", "")
            app_evidence = tool.search(
                f"{objective} architecture components dependencies data flow configuration",
                correlation_id=correlation_id,
                sample_app_id=sample_app_id,
            )
            security_evidence = tool.search(
                f"{objective} hard-coded secret credential PII logging authentication "
                "authorization SQL query injection",
                correlation_id=correlation_id,
                sample_app_id=sample_app_id,
            )
            standards_evidence = tool.search(
                f"{objective} secrets vault PII logging authentication authorization "
                "parameterized queries retention",
                correlation_id=correlation_id,
                source_category="standard",
            )

        evidence = _dedupe_evidence([*app_evidence, *security_evidence, *standards_evidence])
        service_context = MockAssetInventoryTool().get_service_context(sample_app_id)
        metrics["evidence_count"] = len(evidence)
        metrics["retrieval_count"] = 3
        return {
            "retrieved_evidence": evidence,
            "service_context": service_context,
            "status": "analyzing",
        }


def _model_name() -> str:
    return "deterministic-fake" if settings.use_fake_llm else settings.azure_openai_chat_deployment


def _model_architecture_findings(
    state: AssessmentState, evidence: list[RetrievedEvidence]
) -> list[ArchitectureFinding]:
    class _Out(BaseModel):
        findings: list[ArchitectureFinding]

    result = structured_completion(
        _Out,
        prompts.ARCHITECTURE_ANALYST,
        f"Objective: {state['objective']}\n\nEvidence:\n{prompts.format_evidence(evidence)}",
    )
    return result.findings


def _model_risk_findings(
    state: AssessmentState, evidence: list[RetrievedEvidence]
) -> list[RiskFinding]:
    class _Out(BaseModel):
        findings: list[RiskFinding]

    result = structured_completion(
        _Out,
        prompts.SECURITY_ANALYST,
        f"Objective: {state['objective']}\n\nEvidence:\n{prompts.format_evidence(evidence)}",
    )
    return result.findings


def _model_plan(
    state: AssessmentState,
    evidence: list[RetrievedEvidence],
    arch: list[ArchitectureFinding],
    risks: list[RiskFinding],
) -> ModernizationPlan:
    findings_text = "\n".join(
        [f"- [architecture] {f.title}: {f.description}" for f in arch]
        + [f"- [risk/{f.severity}] {f.title}: {f.description}" for f in risks]
    )
    return structured_completion(
        ModernizationPlan,
        prompts.MODERNIZATION_PLANNER,
        f"Objective: {state['objective']}\n\nSupported findings:\n{findings_text}\n\n"
        f"Evidence:\n{prompts.format_evidence(evidence)}",
    )


# The agent call runs inside traced_node so its duration is measured and a
# failure is persisted as node_failed. `model` is set before the call so a
# failed event still names the model that was attempted.
def architecture_analyst_node(state: AssessmentState) -> dict:
    evidence = state.get("retrieved_evidence", [])

    with traced_node(state, "architecture") as metrics:
        metrics["model"] = _model_name()
        findings = (
            fake_agents.fake_architecture_findings(evidence)
            if settings.use_fake_llm
            else _model_architecture_findings(state, evidence)
        )
        metrics["architecture_finding_count"] = len(findings)
        return {"architecture_findings": findings}


def security_analyst_node(state: AssessmentState) -> dict:
    evidence = state.get("retrieved_evidence", [])

    with traced_node(state, "security") as metrics:
        metrics["model"] = _model_name()
        findings = (
            fake_agents.fake_risk_findings(evidence)
            if settings.use_fake_llm
            else _model_risk_findings(state, evidence)
        )
        metrics["risk_finding_count"] = len(findings)
        return {"risk_findings": findings}


def planner_node(state: AssessmentState) -> dict:
    evidence = state.get("retrieved_evidence", [])
    arch = state.get("architecture_findings", [])
    risks = state.get("risk_findings", [])

    with traced_node(state, "planner") as metrics:
        metrics["model"] = _model_name()
        plan = (
            fake_agents.fake_plan(state["objective"], arch, risks, evidence)
            if settings.use_fake_llm
            else _model_plan(state, evidence, arch, risks)
        )
        metrics["option_count"] = len(plan.options)
        return {"modernization_plan": plan, "status": "reviewing"}


def reviewer_node(state: AssessmentState) -> dict:
    """Validate citations, strip unsupported claims, and decide on a revision."""
    decision, kept_arch, kept_risk, cleaned_plan = review(
        state.get("retrieved_evidence", []),
        state.get("architecture_findings", []),
        state.get("risk_findings", []),
        state.get("modernization_plan"),
    )

    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", settings.max_revisions)
    will_revise = decision.revision_requested and revision_count < max_revisions

    with traced_node(state, "reviewer") as metrics:
        metrics["removed_claim_count"] = len(decision.removed_claims)
        metrics["will_revise"] = will_revise
        metrics["revision_count"] = revision_count + 1 if will_revise else revision_count

    return {
        "review_decision": decision,
        "modernization_plan": cleaned_plan,
        "architecture_findings": kept_arch,
        "risk_findings": kept_risk,
        "revision_count": revision_count + 1 if will_revise else revision_count,
        "will_revise": will_revise,
    }


def should_revise(state: AssessmentState) -> str:
    """Read the reviewer's flag, never re-derive it — re-deriving loops forever
    once the revision budget is spent but claims are still unsupported."""
    return "revise" if state.get("will_revise") else "report"


def approval_gate_node(state: AssessmentState) -> dict:
    """Apply the deterministic policy; if approval is required, interrupt() to
    suspend the graph. The Command(resume=...) value returns from interrupt()."""
    request = evaluate_approval_policy(
        state.get("assessment_id", ""),
        state.get("risk_findings", []),
        state.get("modernization_plan"),
    )

    if request is None:
        with traced_node(state, "approval_gate") as metrics:
            metrics["approval_required"] = False
        return {"approval_request": None, "approval_decision": None, "status": "reporting"}

    record_approval_pause(state, request)

    # Blocks here until the API resumes the graph with a decision.
    raw_decision = interrupt(
        {
            "type": "approval_request",
            "assessment_id": request.assessment_id,
            "reasons": request.reasons,
            "highest_severity": request.highest_severity,
            "proposed_action": request.proposed_action,
            "recommended_option": request.recommended_option,
            "estimated_effort": request.estimated_effort,
        }
    )

    decision = _coerce_decision(raw_decision)
    with traced_node(state, "approval_gate") as metrics:
        metrics["approval_required"] = True
        metrics["approved"] = decision.approved
        metrics["approval_reasons"] = request.reasons
    return {
        "approval_request": request.model_dump(mode="json"),
        "approval_decision": decision.model_dump(mode="json"),
        "status": "approved" if decision.approved else "rejected",
    }


def record_approval_pause(state: AssessmentState, request) -> None:
    """Trace the pause itself, so the timeline shows why the run stopped."""
    from app.services.tracing import record_event

    record_event(
        state.get("assessment_id", ""),
        state.get("trace_id", ""),
        "approval_gate",
        "approval_requested",
        payload={"approval_required": True, "approval_reasons": request.reasons},
    )


def _coerce_decision(raw) -> ApprovalDecision:
    """Accept a dict or an ApprovalDecision from the resume payload."""
    if isinstance(raw, ApprovalDecision):
        return raw
    if isinstance(raw, dict):
        return ApprovalDecision(
            approved=bool(raw.get("approved", False)),
            comment=str(raw.get("comment", "")),
            decided_at=raw.get("decided_at"),
        )
    return ApprovalDecision(approved=bool(raw), comment="")


def after_approval(state: AssessmentState) -> str:
    """Only an explicit approval reaches the ticket node."""
    decision = state.get("approval_decision")
    if decision and decision.get("approved") is True:
        return "ticket"
    return "report"


def ticket_node(state: AssessmentState) -> dict:
    """Create the simulated change ticket. The routing edge already guarantees
    approval; the guard below repeats it because "no ticket without approval" is
    a safety property that shouldn't rest on one edge."""
    decision = state.get("approval_decision") or {}
    if decision.get("approved") is not True:
        raise RuntimeError("ticket_node reached without an explicit approval")

    plan = state.get("modernization_plan")
    risks = state.get("risk_findings", [])
    highest = "low"
    for f in risks:
        if SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[highest]:
            highest = f.severity

    request = TicketRequest(
        assessment_id=state.get("assessment_id", ""),
        sample_app_id=state.get("sample_app_id", ""),
        objective=state.get("objective", ""),
        summary=(
            f"Modernization assessment for {state.get('sample_app_id')}: "
            f"{len(risks)} risk finding(s), highest severity {highest}."
        ),
        highest_severity=highest,
        recommended_option=plan.recommended_option if plan else None,
        finding_titles=[f.title for f in risks],
        approval_comment=str(decision.get("comment", "")),
    )

    with traced_node(state, "ticket") as metrics:
        with SessionLocal() as db:
            record = MockServiceNowChangeTool(db).create_assessment_ticket(request)
        metrics["ticket_number"] = record.ticket_number
        metrics["was_existing"] = record.was_existing

    return {"ticket_record": record.model_dump(mode="json"), "status": "reporting"}


def report_node(state: AssessmentState) -> dict:
    """Assemble the auditable final report from validated state."""
    evidence = state.get("retrieved_evidence", [])
    arch = state.get("architecture_findings", [])
    risks = state.get("risk_findings", [])
    plan = state.get("modernization_plan")
    decision = state.get("review_decision")

    risk_register = [
        RiskRegisterEntry(
            severity=f.severity,
            finding=f.title,
            recommended_action=f.recommended_action,
            policy_reference=f.policy_reference,
            evidence_summary=[
                f"{r.file_path}:{r.start_line}-{r.end_line}" for r in f.evidence
            ],
        )
        for f in sorted(risks, key=lambda f: -SEVERITY_ORDER[f.severity])
    ]

    overall = "low"
    for f in risks:
        if SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[overall]:
            overall = f.severity

    files = sorted({e.evidence.file_path for e in evidence})
    critical_count = sum(1 for f in risks if f.severity == "critical")

    summary_parts = [
        f"This assessment reviewed {len(files)} files from the "
        f"{state['sample_app_id']} sample application against the engineering standards.",
    ]
    if risks:
        summary_parts.append(
            f"It identified {len(risks)} risk finding(s), {critical_count} of them critical, "
            f"giving an overall risk level of {overall}."
        )
    else:
        summary_parts.append("No policy violations were identified in the retrieved evidence.")
    if plan:
        summary_parts.append(
            f"The recommended path is '{plan.recommended_option}' at "
            f"{plan.estimated_effort} estimated effort."
        )
    if decision and decision.removed_claims:
        summary_parts.append(
            f"{len(decision.removed_claims)} unsupported claim(s) were removed during review."
        )

    limitations = [
        "Sample data is synthetic; findings do not describe any real production system.",
        "This assessment is advisory and requires expert human review before action.",
        "Analysis covers only the retrieved evidence, not the entire codebase.",
    ]
    if decision and decision.removed_claims:
        limitations.append(
            "Some claims were removed for lacking supporting evidence; see removed_claims."
        )

    approval_request = state.get("approval_request")
    approval_decision = state.get("approval_decision") or {}
    ticket = state.get("ticket_record") or {}
    approval_record = ApprovalRecord(
        approval_required=approval_request is not None,
        approved=approval_decision.get("approved") if approval_decision else None,
        comment=approval_decision.get("comment") or None,
        ticket_number=ticket.get("ticket_number"),
    )
    if approval_request is not None:
        if approval_record.approved:
            summary_parts.append(
                f"A human approved the simulated change ticket "
                f"({approval_record.ticket_number})."
            )
        else:
            summary_parts.append(
                "Human approval was required and not granted, so no change ticket was created."
            )
        limitations.append(
            "Approval authorizes only a simulated change ticket; no code or "
            "infrastructure was modified."
        )

    report = AssessmentReport(
        executive_summary=" ".join(summary_parts),
        scope=ScopeSummary(
            sample_app_id=state["sample_app_id"],
            objective=state["objective"],
            files_reviewed=files,
            evidence_count=len(evidence),
        ),
        architecture_summary=(
            " ".join(f.description for f in arch)
            if arch
            else "No architecture findings were supported by the retrieved evidence."
        ),
        architecture_findings=arch,
        risk_register=risk_register,
        risk_findings=risks,
        plan=plan,
        approval=approval_record,
        removed_claims=decision.removed_claims if decision else [],
        limitations=limitations,
        overall_risk_level=overall,
    )

    with traced_node(state, "report") as metrics:
        metrics["overall_risk_level"] = overall
        metrics["risk_finding_count"] = len(risks)
        metrics["architecture_finding_count"] = len(arch)
        metrics["removed_claim_count"] = len(report.removed_claims)
        metrics["approval_required"] = approval_record.approval_required
        if approval_record.ticket_number:
            metrics["ticket_number"] = approval_record.ticket_number

    return {"final_report": report, "status": "completed"}
