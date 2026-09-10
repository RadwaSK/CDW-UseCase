"""Vector search over document_chunks, reranked without an extra model call.

pgvector cosine distance pulls a candidate pool; each candidate is then scored
alpha * vector_similarity + (1 - alpha) * token-set Jaccard against the query,
favoring chunks that are both semantically close and literally on-topic."""

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_factory import get_embeddings
from app.db.models import DocumentChunk
from app.models.evidence import EvidenceReference, RetrievedEvidence

RERANK_ALPHA = 0.6  # weight on vector similarity vs. lexical overlap
CANDIDATE_POOL_MULTIPLIER = 3  # fetch this many times top_k before reranking

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _lexical_overlap(query_tokens: set[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0
    intersection = query_tokens & content_tokens
    union = query_tokens | content_tokens
    return len(intersection) / len(union) if union else 0.0


def retrieve(
    db: Session,
    query: str,
    *,
    sample_app_id: str | None = None,
    source_category: str | None = None,
    top_k: int | None = None,
) -> list[RetrievedEvidence]:
    """Retrieve the top_k most relevant chunks for `query`, with optional filters.

    source_category="standard" is how the security/governance agent restricts
    itself to engineering_standards evidence instead of app source code.
    """
    top_k = top_k or settings.retrieval_top_k
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)

    stmt = db.query(
        DocumentChunk,
        DocumentChunk.embedding.cosine_distance(query_vector).label("distance"),
    )
    if sample_app_id is not None:
        stmt = stmt.filter(DocumentChunk.sample_app_id == sample_app_id)
    if source_category is not None:
        stmt = stmt.filter(DocumentChunk.source_category == source_category)

    candidates = stmt.order_by("distance").limit(top_k * CANDIDATE_POOL_MULTIPLIER).all()

    query_tokens = _tokenize(query)
    scored: list[RetrievedEvidence] = []
    for row, distance in candidates:
        vector_score = max(0.0, 1.0 - float(distance))
        lexical_score = _lexical_overlap(query_tokens, row.content)
        combined = RERANK_ALPHA * vector_score + (1 - RERANK_ALPHA) * lexical_score
        scored.append(
            RetrievedEvidence(
                evidence=EvidenceReference(
                    file_path=row.file_path,
                    chunk_id=row.id,
                    snippet=row.content,
                    source=Path(row.file_path).name,
                    start_line=row.start_line,
                    end_line=row.end_line,
                ),
                source_category=row.source_category,
                doc_type=row.doc_type,
                score=combined,
                vector_score=vector_score,
                lexical_score=lexical_score,
            )
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
