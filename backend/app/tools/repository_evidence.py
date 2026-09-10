"""Read-only evidence tool over the indexed chunks.

Read-only is structural, not a promise: this wraps retrieval only, exposes no
write path, and takes no caller-supplied filesystem path — the sample app is
chosen from a fixed registry.
"""

from sqlalchemy.orm import Session

from app.models.evidence import RetrievedEvidence
from app.services.retrieval import retrieve
from app.tools.base import timed_call


class RepositoryEvidenceTool:
    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        *,
        correlation_id: str = "",
        sample_app_id: str | None = None,
        source_category: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedEvidence]:
        with timed_call(
            "RepositoryEvidenceTool.search",
            correlation_id,
            sample_app_id=sample_app_id,
            source_category=source_category,
        ) as call:
            results = retrieve(
                self.db,
                query,
                sample_app_id=sample_app_id,
                source_category=source_category,
                top_k=top_k,
            )
            call.fields["result_count"] = len(results)
            return results
