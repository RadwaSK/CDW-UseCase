"""Typed LangGraph state passed between nodes.

Architecture and security analysis run in parallel but write to different keys,
so no reducer is needed for them — only `errors`, which any node may append to.
"""

import operator
from typing import Annotated, TypedDict

from app.models.evidence import RetrievedEvidence
from app.models.findings import ArchitectureFinding, RiskFinding
from app.models.plan import ModernizationPlan
from app.models.report import AssessmentReport
from app.models.review import ReviewDecision


class AssessmentState(TypedDict, total=False):
    assessment_id: str
    status: str
    objective: str
    sample_app_id: str
    trace_id: str

    retrieved_evidence: list[RetrievedEvidence]
    architecture_findings: list[ArchitectureFinding]
    risk_findings: list[RiskFinding]

    modernization_plan: ModernizationPlan | None
    review_decision: ReviewDecision | None
    revision_count: int
    max_revisions: int
    # Set by the reviewer; the conditional edge reads it instead of re-deciding.
    will_revise: bool

    approval_request: dict | None
    approval_decision: dict | None
    ticket_record: dict | None
    # Synthetic CMDB context from the mock asset-inventory tool.
    service_context: dict

    final_report: AssessmentReport | None
    errors: Annotated[list[str], operator.add]
    metrics: dict
