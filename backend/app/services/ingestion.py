"""Chunk + embed sample_data into document_chunks. Idempotent: re-running only
re-embeds chunks whose content_hash changed, and drops rows for chunks a file no
longer produces. Run: python -m app.services.ingestion"""

import hashlib
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.model_factory import get_embeddings
from app.db.models import DocumentChunk
from app.db.session import SessionLocal
from app.services.chunking import chunk_file, doc_type_for
from app.services.sample_apps import SAMPLE_APPS, STANDARDS_FOLDER

logger = logging.getLogger(__name__)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and doc_type_for(path) is not None:
            yield path


def ingest_all() -> dict:
    """Ingest every sample app plus the shared standards; return a counts summary."""
    data_dir = Path(settings.sample_data_dir)
    embeddings = get_embeddings()
    summary = {
        "files": 0,
        "chunks_seen": 0,
        "chunks_embedded": 0,
        "chunks_reused": 0,
        "chunks_deleted": 0,
    }

    with SessionLocal() as db:
        for app in SAMPLE_APPS:
            app_root = data_dir / app.folder
            if not app_root.exists():
                logger.warning("sample_app_folder_missing", extra={"folder": str(app_root)})
                continue
            _ingest_folder(
                db, app_root, data_dir, embeddings, source_category="app",
                sample_app_id=app.id, summary=summary,
            )

        standards_root = data_dir / STANDARDS_FOLDER
        if standards_root.exists():
            _ingest_folder(
                db, standards_root, data_dir, embeddings, source_category="standard",
                sample_app_id=None, summary=summary,
            )

        db.commit()

    logger.info("ingestion_complete", extra=summary)
    return summary


def _ingest_folder(db, root, data_dir, embeddings, *, source_category, sample_app_id, summary):
    for path in _iter_source_files(root):
        rel_path = str(path.relative_to(data_dir)).replace("\\", "/")
        chunks = chunk_file(path)
        summary["files"] += 1
        summary["chunks_seen"] += len(chunks)

        existing = {
            row.chunk_index: row
            for row in db.scalars(
                select(DocumentChunk).where(DocumentChunk.file_path == rel_path)
            )
        }

        texts_to_embed: list[str] = []
        rows_needing_embedding: list[DocumentChunk] = []

        for idx, chunk in enumerate(chunks):
            content_hash = _content_hash(chunk.content)
            row = existing.get(idx)

            if row is not None and row.content_hash == content_hash:
                summary["chunks_reused"] += 1
                continue

            if row is None:
                row = DocumentChunk(
                    sample_app_id=sample_app_id,
                    source_category=source_category,
                    file_path=rel_path,
                    chunk_index=idx,
                )
                db.add(row)

            row.doc_type = chunk.doc_type
            row.start_line = chunk.start_line
            row.end_line = chunk.end_line
            row.content = chunk.content
            row.content_hash = content_hash
            texts_to_embed.append(chunk.content)
            rows_needing_embedding.append(row)

        if texts_to_embed:
            vectors = embeddings.embed_documents(texts_to_embed)
            # strict=True: a short vector list must fail, not leave chunks unembedded.
            for row, vector in zip(rows_needing_embedding, vectors, strict=True):
                row.embedding = vector
            summary["chunks_embedded"] += len(texts_to_embed)

        # Drop stale chunks left over from a file that shrank.
        stale_indices = [i for i in existing if i >= len(chunks)]
        for idx in stale_indices:
            db.delete(existing[idx])
            summary["chunks_deleted"] += 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = ingest_all()
    print(result)
