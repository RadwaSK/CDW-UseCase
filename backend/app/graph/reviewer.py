"""Evidence validation: deterministic, not a model call. Every citation is checked
against the retrieved chunk ids, so a fabricated or dangling reference is caught
mechanically — asking an LLM to grade its own grounding is the weakest check."""

from app.models.evidence import RetrievedEvidence
from app.models.findings import ArchitectureFinding, RiskFinding
from app.models.plan import ModernizationPlan
from app.models.review import RemovedClaim, ReviewDecision


def _valid_chunk_ids(evidence: list[RetrievedEvidence]) -> set[str]:
    return {e.evidence.chunk_id for e in evidence}


def _supported(refs, valid_ids: set[str]) -> bool:
    return bool(refs) and all(r.chunk_id in valid_ids and r.snippet.strip() for r in refs)


def review(
    evidence: list[RetrievedEvidence],
    architecture_findings: list[ArchitectureFinding],
    risk_findings: list[RiskFinding],
    plan: ModernizationPlan | None,
) -> tuple[ReviewDecision, list[ArchitectureFinding], list[RiskFinding], ModernizationPlan | None]:
    """Strip unsupported claims. Returns the decision plus the cleaned outputs."""
    valid_ids = _valid_chunk_ids(evidence)
    removed: list[RemovedClaim] = []

    kept_arch = []
    for f in architecture_findings:
        if _supported(f.evidence, valid_ids):
            kept_arch.append(f)
        else:
            removed.append(
                RemovedClaim(
                    claim=f.title,
                    reason="Architecture finding cited evidence not present in the retrieved set.",
                )
            )

    kept_risk = []
    for f in risk_findings:
        if _supported(f.evidence, valid_ids):
            kept_risk.append(f)
        else:
            removed.append(
                RemovedClaim(
                    claim=f.title,
                    reason="Risk finding cited evidence not present in the retrieved set.",
                )
            )

    cleaned_plan = plan
    if plan is not None:
        # Drop an option with a dangling citation whole — stripping just the
        # citation would leave a claim with nothing behind it.
        kept_options = []
        for option in plan.options:
            bad_refs = [r for r in option.evidence if r.chunk_id not in valid_ids]
            if bad_refs:
                removed.append(
                    RemovedClaim(
                        claim=f"Modernization option: {option.name}",
                        reason=(
                            f"{len(bad_refs)} citation(s) referenced evidence not in the "
                            "retrieved set, so the option could not be verified."
                        ),
                    )
                )
            else:
                kept_options.append(option)

        plan_refs_ok = [r for r in plan.evidence if r.chunk_id in valid_ids]
        dangling_plan_refs = len(plan.evidence) - len(plan_refs_ok)
        if dangling_plan_refs:
            removed.append(
                RemovedClaim(
                    claim="Plan-level supporting evidence",
                    reason=(
                        f"{dangling_plan_refs} plan citation(s) referenced chunks not in "
                        "the retrieved evidence and were dropped."
                    ),
                )
            )

        update = {"evidence": plan_refs_ok, "options": kept_options}

        # If the recommendation pointed at a dropped option, fall back to a survivor.
        if kept_options and plan.recommended_option not in {o.name for o in kept_options}:
            removed.append(
                RemovedClaim(
                    claim=f"Recommended option '{plan.recommended_option}'",
                    reason=(
                        "The recommended option was removed or never offered; the "
                        "recommendation fell back to a verifiable option."
                    ),
                )
            )
            update["recommended_option"] = kept_options[0].name

        cleaned_plan = plan.model_copy(update=update)

    decision = ReviewDecision(
        approved=not removed,
        revision_requested=bool(removed),
        removed_claims=removed,
        notes=(
            "All findings and plan citations resolve to retrieved evidence."
            if not removed
            else f"Removed {len(removed)} unsupported claim(s); requested one revision."
        ),
    )
    return decision, kept_arch, kept_risk, cleaned_plan
