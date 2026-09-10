"""Structured outputs from the analyst agents. Every finding must cite evidence."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceReference

Severity = Literal["low", "medium", "high", "critical"]
Effort = Literal["low", "medium", "high"]


class ArchitectureFinding(BaseModel):
    """A component, dependency, data-flow, or technical-debt observation."""

    category: Literal["component", "dependency", "data_flow", "technical_debt"]
    title: str
    description: str
    evidence: list[EvidenceReference] = Field(..., min_length=1)
    # A communication device for the reader, not a calibrated probability.
    confidence: float = Field(..., ge=0.0, le=1.0)


class RiskFinding(BaseModel):
    """A policy violation or security/governance risk, tied to a standard."""

    category: Literal["secret", "pii", "auth", "injection", "data_retention", "other"]
    title: str
    description: str
    severity: Severity
    recommended_action: str
    # Which engineering standard this violates, e.g. "security_standard.md".
    policy_reference: str
    evidence: list[EvidenceReference] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
