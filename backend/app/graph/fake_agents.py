"""Deterministic rule-based stand-ins for the analyst/planner agents.

Used whenever settings.use_fake_llm is True (always in tests). These are not
pretending to be an LLM — they are keyword/pattern detectors over the same
retrieved evidence the real agents see, so tests can assert exact findings
without a live model call. Every finding cites the chunk that triggered it,
which is what the evidence reviewer later validates.
"""

import re

from app.models.evidence import EvidenceReference, RetrievedEvidence
from app.models.findings import ArchitectureFinding, RiskFinding
from app.models.plan import ModernizationOption, ModernizationPlan, RoadmapPhase

# A chunk id the reviewer will not find in the evidence set — used to simulate an
# LLM overreaching on a request the evidence doesn't support. See fake_plan().
FABRICATED_CHUNK_ID = "00000000-0000-0000-0000-000000000000"

# A credential-shaped name assigned a *string literal*. Reading the same name
# from the environment is the correct pattern and must not be flagged, so the
# env-lookup case is excluded explicitly rather than matched on the name alone.
_SECRET_ASSIGNMENT_RE = re.compile(
    r"""(?im)^\s*\w*(?:api_key|secret|token|password|credential)\w*\s*=\s*['"][^'"]+['"]"""
)
_ENV_LOOKUP_RE = re.compile(r"os\.(environ|getenv)")


def _has_hardcoded_secret(content: str) -> bool:
    for line in content.splitlines():
        if _SECRET_ASSIGNMENT_RE.match(line) and not _ENV_LOOKUP_RE.search(line):
            return True
    return False


_LOG_CALL_RE = re.compile(r"\b(?:logger|logging|log)\.(?:debug|info|warning|error|critical)\s*\(")
_PII_TERM_RE = re.compile(r"(?i)\b(customer|email|phone|address|ssn|full_name|pii)\b")
# A whole record passed straight to the formatter, e.g. `..., row)` — as opposed
# to a derived value like `row is not None`.
_BARE_RECORD_ARG_RE = re.compile(r",\s*(row|record|user|customer|item)\s*\)")


def _logs_pii(content: str) -> bool:
    """True only when a log call actually carries PII.

    Naively matching a word like "row" anywhere in the chunk flags correct code
    that logs a lookup key and a boolean, so the check is scoped to the logging
    call itself and to what it passes.
    """
    for line in content.splitlines():
        if not _LOG_CALL_RE.search(line):
            continue
        if _PII_TERM_RE.search(line) or _BARE_RECORD_ARG_RE.search(line):
            return True
    return False


def _ref(item: RetrievedEvidence) -> EvidenceReference:
    return item.evidence


def _app_evidence(evidence: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
    return [e for e in evidence if e.source_category == "app"]


def fake_architecture_findings(evidence: list[RetrievedEvidence]) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    for item in _app_evidence(evidence):
        content = item.evidence.snippet
        path = item.evidence.file_path

        if "Flask(" in content or "@app.route" in content:
            findings.append(
                ArchitectureFinding(
                    category="component",
                    title="Flask HTTP layer with request handlers",
                    description=(
                        "The service exposes HTTP endpoints via Flask, with business logic "
                        "written directly inside the request handlers rather than a "
                        "separate service layer."
                    ),
                    evidence=[_ref(item)],
                    confidence=0.9,
                )
            )
        if "sqlite3" in content or "get_connection" in content:
            findings.append(
                ArchitectureFinding(
                    category="dependency",
                    title="Direct, hand-rolled database connections",
                    description=(
                        "Database access opens connections directly per call with no pooling, "
                        "no managed service, and no ORM layer."
                    ),
                    evidence=[_ref(item)],
                    confidence=0.9,
                )
            )
        if "dataclass" in content and ("Customer" in content or "Order" in content):
            findings.append(
                ArchitectureFinding(
                    category="data_flow",
                    title="Customer and order data model carries PII fields",
                    description=(
                        "Order records reference a Customer carrying email, phone, and "
                        "shipping address, so PII flows through the order lifecycle."
                    ),
                    evidence=[_ref(item)],
                    confidence=0.85,
                )
            )
        if "DEBUG = True" in content or "debug=True" in content:
            findings.append(
                ArchitectureFinding(
                    category="technical_debt",
                    title="Debug mode enabled in configuration",
                    description=(
                        "Debug flags are hard-coded on, which is not deployable and "
                        "indicates configuration is not environment-aware."
                    ),
                    evidence=[_ref(item)],
                    confidence=0.8,
                )
            )
        if path.endswith("config.py") and "os.environ" not in content:
            findings.append(
                ArchitectureFinding(
                    category="technical_debt",
                    title="Configuration is hard-coded rather than environment-driven",
                    description=(
                        "Hosts, database names, and flags are literals in source, so the "
                        "service cannot be promoted across environments without a code change."
                    ),
                    evidence=[_ref(item)],
                    confidence=0.85,
                )
            )
    return _dedupe_by_title(findings)


def fake_risk_findings(evidence: list[RetrievedEvidence]) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    for item in _app_evidence(evidence):
        content = item.evidence.snippet

        if _has_hardcoded_secret(content):
            findings.append(
                RiskFinding(
                    category="secret",
                    title="Hard-coded credential placeholder in source",
                    description=(
                        "A payment gateway API key is assigned as a string literal in "
                        "configuration instead of being read from a managed vault."
                    ),
                    severity="critical",
                    recommended_action=(
                        "Move the credential to a managed secrets vault (e.g. Azure Key Vault) "
                        "and inject it at runtime; rotate any real key with the same name."
                    ),
                    policy_reference="security_standard.md",
                    evidence=[_ref(item)],
                    confidence=0.95,
                )
            )
        if _logs_pii(content):
            findings.append(
                RiskFinding(
                    category="pii",
                    title="Customer record containing PII written to logs",
                    description=(
                        "A full customer row, including email and address, is logged at "
                        "INFO level on every lookup."
                    ),
                    severity="critical",
                    recommended_action=(
                        "Remove the PII from the log statement; log a non-identifying "
                        "correlation id instead."
                    ),
                    policy_reference="security_standard.md",
                    evidence=[_ref(item)],
                    confidence=0.95,
                )
            )
        if 'f"SELECT' in content or "WHERE email = '{" in content:
            findings.append(
                RiskFinding(
                    category="injection",
                    title="Unparameterized SQL built from request input",
                    description=(
                        "A query is assembled with string formatting from a caller-supplied "
                        "email value rather than bound parameters."
                    ),
                    severity="high",
                    recommended_action=(
                        "Replace string-formatted SQL with parameterized queries or ORM "
                        "parameter binding."
                    ),
                    policy_reference="security_standard.md",
                    evidence=[_ref(item)],
                    confidence=0.9,
                )
            )
        if "No authentication" in content or "no authentication" in content:
            findings.append(
                RiskFinding(
                    category="auth",
                    title="State-changing endpoint with no authorization check",
                    description=(
                        "The order-creation endpoint mutates business data without "
                        "authenticating or authorizing the caller."
                    ),
                    severity="high",
                    recommended_action=(
                        "Enforce authentication and role-based authorization on all "
                        "state-changing endpoints."
                    ),
                    policy_reference="security_standard.md",
                    evidence=[_ref(item)],
                    confidence=0.9,
                )
            )
    return _dedupe_by_title(findings)


def _asks_about_rewrite(objective: str) -> bool:
    """Matches rewrite/rewritten/rewriting — the stem, not the exact word."""
    return "rewrit" in objective.lower()


def fake_plan(
    objective: str,
    architecture_findings: list[ArchitectureFinding],
    risk_findings: list[RiskFinding],
    evidence: list[RetrievedEvidence],
) -> ModernizationPlan:
    critical_or_high = [f for f in risk_findings if f.severity in {"critical", "high"}]
    touches_auth = any(f.category == "auth" for f in risk_findings)
    plan_evidence = [_ref(e) for e in evidence[:3]]

    options = [
        ModernizationOption(
            name="Remediate in place, then containerize",
            description=(
                "Fix the critical security findings against the existing codebase, add "
                "structured logging and health checks, then containerize and move "
                "configuration to environment variables."
            ),
            trade_offs=(
                "Lowest risk and fastest to value, but leaves the existing Flask "
                "structure and hand-rolled data layer in place."
            ),
            effort="medium",
            risk_reduction="Removes all critical secret/PII findings before any migration.",
            addresses=[f.title for f in critical_or_high],
        ),
        ModernizationOption(
            name="Strangler-fig extraction to a managed platform",
            description=(
                "Stand up a new service alongside the legacy one and migrate endpoints "
                "incrementally, backed by a managed database."
            ),
            trade_offs=(
                "Higher effort and longer timeline, but retires the legacy data layer "
                "and gives a clean deployment story."
            ),
            effort="high",
            risk_reduction="Addresses architectural debt as well as the security findings.",
            addresses=[f.title for f in architecture_findings],
        ),
    ]

    # Simulates an LLM overreaching when asked something the evidence can't answer:
    # a rewrite recommendation citing a chunk that isn't in the evidence set. The
    # evidence reviewer detects the dangling citation and removes it.
    if _asks_about_rewrite(objective):
        options.append(
            ModernizationOption(
                name="Full rewrite in a new language",
                description=(
                    "Rewrite the service from scratch in a different language and framework."
                ),
                trade_offs="Highest cost and risk.",
                effort="high",
                risk_reduction="Claimed to resolve all findings at once.",
                addresses=["Full rewrite"],
                evidence=[
                    EvidenceReference(
                        file_path="legacy_order_service/app.py",
                        chunk_id=FABRICATED_CHUNK_ID,
                        snippet="(claimed evidence for a full rewrite)",
                        source="app.py",
                        start_line=1,
                        end_line=1,
                    )
                ],
            )
        )

    effort = "high" if len(critical_or_high) >= 3 or touches_auth else "medium"
    now_items = [f"Remediate: {f.title}" for f in critical_or_high] or [
        "Add structured logging and a health endpoint"
    ]

    plan = ModernizationPlan(
        summary=(
            "Remediate the critical security findings first, then modernize the "
            "runtime and data layer in phases."
        ),
        options=options,
        recommended_option="Remediate in place, then containerize",
        recommendation_rationale=(
            "The evidence shows concrete, individually fixable security defects rather "
            "than an unsalvageable architecture, so incremental remediation delivers the "
            "risk reduction fastest."
        ),
        roadmap=[
            RoadmapPhase(phase="now", items=now_items),
            RoadmapPhase(
                phase="next",
                items=[
                    "Externalize configuration and containerize the service",
                    "Add health and readiness endpoints",
                ],
            ),
            RoadmapPhase(
                phase="later",
                items=["Migrate to a managed database service", "Decommission legacy hosts"],
            ),
        ],
        estimated_effort=effort,
        touches_auth=touches_auth,
        evidence=plan_evidence,
    )

    return plan


def _dedupe_by_title(findings: list) -> list:
    seen = set()
    out = []
    for f in findings:
        if f.title not in seen:
            seen.add(f.title)
            out.append(f)
    return out
