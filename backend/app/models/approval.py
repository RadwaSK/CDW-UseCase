"""Approval request/decision and ticket schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.findings import Effort, Severity


class ApprovalRequest(BaseModel):
    """Why a human decision is required, and exactly what is being asked for."""

    assessment_id: str
    reasons: list[str] = Field(..., min_length=1)
    highest_severity: Severity
    proposed_action: str
    recommended_option: str | None = None
    estimated_effort: Effort | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    comment: str = ""
    decided_at: datetime | None = None


class TicketRequest(BaseModel):
    """Validated input to the change-management tool."""

    assessment_id: str
    sample_app_id: str
    objective: str
    summary: str
    highest_severity: Severity
    recommended_option: str | None = None
    finding_titles: list[str] = Field(default_factory=list)
    approval_comment: str = ""


class TicketRecord(BaseModel):
    ticket_number: str
    assessment_id: str
    status: str
    created_at: datetime
    summary: str
    # True when an existing ticket was returned instead of creating a second one.
    was_existing: bool = False
