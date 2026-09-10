"""Request/response schemas for the assessment endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.report import AssessmentReport


class AssessmentCreateRequest(BaseModel):
    sample_app_id: str
    objective: str = Field(..., min_length=1, max_length=2000)


class AssessmentResponse(BaseModel):
    id: str
    sample_app_id: str
    objective: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssessmentDetailResponse(AssessmentResponse):
    """Assessment plus its report, and the approval request if it's paused."""

    report: AssessmentReport | None = None
    pending_approval: dict | None = None


class ApprovalSubmission(BaseModel):
    approved: bool
    comment: str = Field("", max_length=2000)


class TraceEventResponse(BaseModel):
    node: str
    event_type: str
    duration_ms: int | None = None
    payload: dict = Field(default_factory=dict)
    error_class: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
