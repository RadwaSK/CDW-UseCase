"""Modernization plan produced by the planner agent."""

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceReference
from app.models.findings import Effort


class ModernizationOption(BaseModel):
    name: str
    description: str
    trade_offs: str
    effort: Effort
    risk_reduction: str
    # Which findings this option addresses (finding titles).
    addresses: list[str] = Field(default_factory=list)
    # Each option is a claim in its own right, so it carries its own citations
    # and the reviewer can reject one option without discarding the whole plan.
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RoadmapPhase(BaseModel):
    phase: str  # "now" | "next" | "later"
    items: list[str]


class ModernizationPlan(BaseModel):
    summary: str
    options: list[ModernizationOption] = Field(..., min_length=1)
    recommended_option: str
    recommendation_rationale: str
    roadmap: list[RoadmapPhase]
    estimated_effort: Effort
    # Recommended work touches authn/authz — an approval-policy trigger.
    touches_auth: bool = False
    evidence: list[EvidenceReference] = Field(default_factory=list)
