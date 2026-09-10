"""Evidence-reference schemas — every finding downstream must cite one of these."""

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    file_path: str
    chunk_id: str
    snippet: str = Field(..., description="Quoted/extracted text supporting the finding")
    source: str = Field(..., description="Policy or file name this evidence comes from")
    start_line: int
    end_line: int


class RetrievedEvidence(BaseModel):
    evidence: EvidenceReference
    source_category: str  # "app" | "standard"
    doc_type: str
    score: float = Field(..., description="Final reranked relevance score")
    vector_score: float
    lexical_score: float
