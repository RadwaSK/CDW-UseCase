"""Deterministic approval policy — a pure function, never a model decision.

Whether a human must sign off is a governance rule, so it is evaluated from the
structured findings with explicit, auditable reasons. Approval permits only the
creation of a *simulated* change ticket; it never authorizes code changes or
deployment.
"""

from app.models.approval import ApprovalRequest
from app.models.findings import RiskFinding
from app.models.plan import ModernizationPlan

# Finding categories that always require a human decision.
SENSITIVE_CATEGORIES = {"pii", "secret"}


def evaluate_approval_policy(
    assessment_id: str,
    risk_findings: list[RiskFinding],
    plan: ModernizationPlan | None,
) -> ApprovalRequest | None:
    """Return an ApprovalRequest if sign-off is required, else None.

    Triggers (any one is sufficient):
      - a critical finding exists
      - PII exposure or a hard-coded secret was detected
      - the recommended work touches authentication/authorization
      - estimated effort is high
    """
    reasons: list[str] = []

    critical = [f for f in risk_findings if f.severity == "critical"]
    if critical:
        reasons.append(
            f"{len(critical)} critical finding(s): " + "; ".join(f.title for f in critical)
        )

    sensitive = [f for f in risk_findings if f.category in SENSITIVE_CATEGORIES]
    if sensitive:
        kinds = sorted({f.category for f in sensitive})
        reasons.append(f"Sensitive exposure detected ({', '.join(kinds)})")

    if plan is not None and plan.touches_auth:
        reasons.append("Recommended work changes authentication/authorization")

    if plan is not None and plan.estimated_effort == "high":
        reasons.append("Estimated effort is high")

    if not reasons:
        return None

    highest = "low"
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for f in risk_findings:
        if order[f.severity] > order[highest]:
            highest = f.severity

    return ApprovalRequest(
        assessment_id=assessment_id,
        reasons=reasons,
        highest_severity=highest,
        proposed_action=(
            "Create a simulated ServiceNow change ticket recording this assessment's "
            "findings and recommended remediation. No code or infrastructure is modified."
        ),
        recommended_option=plan.recommended_option if plan else None,
        estimated_effort=plan.estimated_effort if plan else None,
    )
