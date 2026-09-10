"""Evidence reviewer output — the hallucination control point."""

from pydantic import BaseModel, Field


class RemovedClaim(BaseModel):
    """A claim the reviewer rejected, kept for the report's limitations section."""

    claim: str
    reason: str


class ReviewDecision(BaseModel):
    approved: bool
    revision_requested: bool
    removed_claims: list[RemovedClaim] = Field(default_factory=list)
    notes: str = ""
