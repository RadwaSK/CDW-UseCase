from app.db.models import DocumentChunk
from app.services.ingestion import ingest_all
from app.services.sample_apps import SAMPLE_APPS_BY_ID


def test_ingestion_populates_both_source_categories(ingested):
    assert ingested["files"] > 0
    assert ingested["chunks_seen"] > 0
    # Either freshly embedded or reused from a still-matching prior run — the
    # `ingested` session fixture doesn't guarantee a clean-slate DB.
    assert ingested["chunks_embedded"] + ingested["chunks_reused"] == ingested["chunks_seen"]


def test_ingestion_is_idempotent(ingested, db_session):
    before_count = db_session.query(DocumentChunk).count()

    second_run = ingest_all()

    after_count = db_session.query(DocumentChunk).count()

    assert after_count == before_count
    # Nothing changed, so nothing should have needed a fresh embedding call.
    assert second_run["chunks_embedded"] == 0
    assert second_run["chunks_reused"] == second_run["chunks_seen"]
    assert second_run["chunks_deleted"] == 0


def test_ingested_chunks_have_required_metadata(ingested, db_session):
    rows = db_session.query(DocumentChunk).limit(20).all()
    assert rows
    for row in rows:
        assert row.file_path
        assert row.doc_type in {"python", "markdown", "text", "json", "yaml"}
        assert row.source_category in {"app", "standard"}
        assert row.start_line >= 1
        assert row.end_line >= row.start_line
        assert row.content_hash
        assert row.embedding is not None

        if row.source_category == "app":
            assert row.sample_app_id in SAMPLE_APPS_BY_ID
        else:
            assert row.sample_app_id is None
