from app.services.retrieval import retrieve


def test_retrieve_filters_by_source_category_standard(ingested, db_session):
    results = retrieve(
        db_session,
        "secrets must use a vault",
        source_category="standard",
        top_k=6,
    )

    assert results
    for r in results:
        assert r.source_category == "standard"
        assert r.evidence.file_path.startswith("engineering_standards/")


def test_retrieve_filters_by_sample_app_id(ingested, db_session):
    results = retrieve(
        db_session,
        "hard-coded API key",
        sample_app_id="legacy_order_service",
        top_k=6,
    )

    assert results
    for r in results:
        assert r.source_category == "app"
        assert r.evidence.file_path.startswith("legacy_order_service/")


def test_retrieve_returns_valid_evidence_references(ingested, db_session):
    results = retrieve(db_session, "customer email logged", top_k=4)

    assert results
    for r in results:
        ev = r.evidence
        assert ev.file_path
        assert ev.chunk_id
        assert ev.snippet.strip()
        assert ev.source == ev.file_path.split("/")[-1]
        assert ev.start_line >= 1
        assert ev.end_line >= ev.start_line
        assert r.score >= 0.0
        assert r.vector_score >= 0.0
        assert 0.0 <= r.lexical_score <= 1.0


def test_retrieve_respects_top_k(ingested, db_session):
    results = retrieve(db_session, "order service architecture", top_k=2)
    assert len(results) <= 2


def test_secret_query_surfaces_config_chunk_high(ingested, db_session):
    results = retrieve(
        db_session,
        "hard coded payment gateway api key should be in key vault",
        sample_app_id="legacy_order_service",
        top_k=6,
    )

    file_paths = [r.evidence.file_path for r in results]
    assert any(p.endswith("config.py") for p in file_paths)
