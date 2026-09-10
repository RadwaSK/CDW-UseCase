"""Assessment endpoints: create/run, approve/resume, and read results and trace."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assessment, TraceEvent
from app.db.session import get_db
from app.graph.workflow import (
    get_assessment_state,
    get_pending_approval,
    is_awaiting_approval,
    resume_with_decision,
    run_assessment,
)
from app.models.assessment import (
    ApprovalSubmission,
    AssessmentCreateRequest,
    AssessmentDetailResponse,
    TraceEventResponse,
)
from app.models.report import AssessmentReport
from app.services.sample_apps import SAMPLE_APPS_BY_ID

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assessments"])


@router.post("/assessments", response_model=AssessmentDetailResponse, status_code=201)
def create_assessment(
    payload: AssessmentCreateRequest, db: Session = Depends(get_db)
) -> AssessmentDetailResponse:
    """Create the record and run the workflow until it completes or pauses."""
    if payload.sample_app_id not in SAMPLE_APPS_BY_ID:
        raise HTTPException(422, f"Unknown sample_app_id: {payload.sample_app_id!r}")

    assessment = Assessment(
        sample_app_id=payload.sample_app_id,
        objective=payload.objective,
        status="pending",
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    try:
        state = run_assessment(assessment.id, payload.objective, payload.sample_app_id)
    except Exception as exc:
        logger.exception("assessment_run_failed", extra={"assessment_id": assessment.id})
        assessment.status = "failed"
        db.commit()
        raise HTTPException(500, "Assessment failed to complete. See server logs.") from exc

    return _persist_and_respond(db, assessment, state)


@router.post(
    "/assessments/{assessment_id}/approval", response_model=AssessmentDetailResponse
)
def submit_approval(
    assessment_id: str, payload: ApprovalSubmission, db: Session = Depends(get_db)
) -> AssessmentDetailResponse:
    """Resume a paused graph with a human decision.

    Approval permits only the simulated change ticket — never code changes or
    deployment.
    """
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment {assessment_id} not found")

    if not is_awaiting_approval(assessment_id):
        raise HTTPException(
            409,
            f"Assessment {assessment_id} is not awaiting approval "
            f"(status: {assessment.status}).",
        )

    try:
        state = resume_with_decision(assessment_id, payload.approved, payload.comment)
    except Exception as exc:
        logger.exception("approval_resume_failed", extra={"assessment_id": assessment_id})
        raise HTTPException(500, "Failed to resume the assessment. See server logs.") from exc

    return _persist_and_respond(db, assessment, state)


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse)
def get_assessment(assessment_id: str, db: Session = Depends(get_db)) -> AssessmentDetailResponse:
    assessment = _require(db, assessment_id)
    report = AssessmentReport.model_validate(assessment.state) if assessment.state else None
    return _to_detail(assessment, report)


@router.get("/assessments/{assessment_id}/report", response_model=AssessmentReport)
def get_assessment_report(assessment_id: str, db: Session = Depends(get_db)) -> AssessmentReport:
    assessment = _require(db, assessment_id)
    if not assessment.state:
        raise HTTPException(409, f"Assessment {assessment_id} has no report yet")
    return AssessmentReport.model_validate(assessment.state)


@router.get(
    "/assessments/{assessment_id}/trace", response_model=list[TraceEventResponse]
)
def get_assessment_trace(
    assessment_id: str, db: Session = Depends(get_db)
) -> list[TraceEventResponse]:
    """Sanitized execution trace: node timings and counts, never prompts or reasoning."""
    _require(db, assessment_id)
    events = db.scalars(
        select(TraceEvent)
        .where(TraceEvent.assessment_id == assessment_id)
        .order_by(TraceEvent.created_at)
    ).all()
    return [TraceEventResponse.model_validate(e) for e in events]


@router.get("/assessments/{assessment_id}/state")
def get_checkpointed_state(assessment_id: str) -> dict:
    """Current LangGraph checkpoint state — proves the run is resumable."""
    state = get_assessment_state(assessment_id)
    if state is None:
        raise HTTPException(404, f"No checkpointed state for assessment {assessment_id}")
    return {
        "assessment_id": state.get("assessment_id"),
        "status": state.get("status"),
        "awaiting_approval": is_awaiting_approval(assessment_id),
        "revision_count": state.get("revision_count"),
        "max_revisions": state.get("max_revisions"),
        "evidence_count": len(state.get("retrieved_evidence", [])),
        "architecture_finding_count": len(state.get("architecture_findings", [])),
        "risk_finding_count": len(state.get("risk_findings", [])),
        "errors": state.get("errors", []),
    }


def _require(db: Session, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment {assessment_id} not found")
    return assessment


def _persist_and_respond(
    db: Session, assessment: Assessment, state: dict
) -> AssessmentDetailResponse:
    """Store the report/status and build the response, including a pending approval."""
    awaiting = is_awaiting_approval(assessment.id)
    report = state.get("final_report")

    assessment.status = "awaiting_approval" if awaiting else state.get("status", "completed")
    if report is not None:
        assessment.state = report.model_dump(mode="json")
    db.commit()
    db.refresh(assessment)

    return _to_detail(
        assessment,
        report,
        pending_approval=get_pending_approval(assessment.id) if awaiting else None,
    )


def _to_detail(
    assessment: Assessment,
    report: AssessmentReport | None,
    pending_approval: dict | None = None,
) -> AssessmentDetailResponse:
    return AssessmentDetailResponse(
        id=assessment.id,
        sample_app_id=assessment.sample_app_id,
        objective=assessment.objective,
        status=assessment.status,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
        report=report,
        pending_approval=pending_approval,
    )
