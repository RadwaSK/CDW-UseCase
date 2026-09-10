"""Final assessment report — the auditable output, shaped per the build brief."""

from pydantic import BaseModel, Field

from app.models.findings import ArchitectureFinding, RiskFinding, Severity
from app.models.plan import ModernizationPlan
from app.models.review import RemovedClaim


class ScopeSummary(BaseModel):
    sample_app_id: str
    objective: str
    files_reviewed: list[str]
    evidence_count: int


class RiskRegisterEntry(BaseModel):
    severity: Severity
    finding: str
    recommended_action: str
    policy_reference: str
    evidence_summary: list[str]  # "file_path:start-end" locators


class ApprovalRecord(BaseModel):
    """Populated in Phase 3 once the approval gate and ticket tool exist."""

    approval_required: bool
    approved: bool | None = None
    comment: str | None = None
    ticket_number: str | None = None


class AssessmentReport(BaseModel):
    executive_summary: str
    scope: ScopeSummary
    architecture_summary: str
    architecture_findings: list[ArchitectureFinding] = Field(default_factory=list)
    risk_register: list[RiskRegisterEntry] = Field(default_factory=list)
    risk_findings: list[RiskFinding] = Field(default_factory=list)
    plan: ModernizationPlan | None = None
    approval: ApprovalRecord | None = None
    removed_claims: list[RemovedClaim] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    overall_risk_level: Severity = "low"
