from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
MIGRATION_PATH = (
    REPO_ROOT / "migrations/20260831000019_post_content_features.sql"
)
CONTRACT_PATH = REPO_ROOT / "docs/contracts/post-content-features-v1.md"
BENCHMARK_PATH = (
    REPO_ROOT
    / "tests/fixtures/post_content_features/vietnamese-retrieval-v1.json"
)
SQL_FIXTURE_PATH = (
    REPO_ROOT / "tests/fixtures/post_content_features/migration_contract.sql"
)
MIGRATION_HARNESS_PATH = (
    REPO_ROOT / "tests/test_post_content_features_migration.sh"
)

ENCODER_VERSION = (
    "intfloat/multilingual-e5-small@"
    "614241f622f53c4eeff9890bdc4f31cfecc418b3"
)
MODEL_SHA256 = (
    "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_migration_is_additive_and_declares_feature_identity():
    migration = _read(MIGRATION_PATH)
    normalized = " ".join(migration.lower().split())

    assert "create table post_content_encoder_versions" in normalized
    assert "create table post_content_features" in normalized
    assert "alter table posts" not in normalized
    assert "drop table posts" not in normalized
    assert re.search(r"post_id\s+uuid\s+not null", migration, re.IGNORECASE)
    assert re.search(r"encoder_version\s+text\s+not null", migration, re.IGNORECASE)
    assert re.search(r"embedding\s+real\[\]\s+not null", migration, re.IGNORECASE)
    assert re.search(r"normalized_topics\s+text\[\]\s+not null", migration, re.IGNORECASE)
    assert re.search(r"content_hash\s+text\s+not null", migration, re.IGNORECASE)
    assert "source_updated_at" in normalized
    assert "computed_at" in normalized
    assert "unique (post_id, encoder_version, content_hash)" in normalized
    assert "on delete cascade" in normalized


def test_migration_rejects_invalid_versions_dimensions_hashes_and_topics():
    migration = _read(MIGRATION_PATH)
    normalized = " ".join(migration.lower().split())

    assert "references post_content_encoder_versions" in normalized
    assert "post_content_embedding_is_valid(embedding, 384)" in normalized
    assert "content_hash ~ '^[0-9a-f]{64}$'" in normalized
    assert "post_content_topics_are_normalized(normalized_topics)" in normalized
    assert "prevent_post_content_feature_mutation" in normalized
    assert "prevent_post_content_encoder_mutation" in normalized
    assert (
        "encoder_version = model_repository || '@' || model_revision"
        in normalized
    )
    assert re.search(
        r"encoder_version\s*~\s*"
        r"'\^\[a-za-z0-9\]\[a-za-z0-9\._-\]\*"
        r"/\[a-za-z0-9\]\[a-za-z0-9\._-\]\*"
        r"@\[0-9a-f\]\{40\}\$'",
        normalized,
    )
    assert "before update or delete on post_content_features" in normalized
    assert "pg_trigger_depth() > 1" in normalized
    assert ENCODER_VERSION in migration
    assert MODEL_SHA256 in migration


def test_contract_pins_encoder_payload_normalization_and_fallback():
    contract = _read(CONTRACT_PATH)

    for expected in (
        "post-content-features-v1",
        ENCODER_VERSION,
        MODEL_SHA256,
        "MIT",
        "384",
        "Unicode NFC",
        "passage: ",
        "query: ",
        "512",
        "L2",
        "keyword topics",
        "source_updated_at <= served_at",
        "computed_at <= served_at",
    ):
        assert expected in contract

    assert "raw `post_id`" in contract
    assert "must not" in contract


def test_vietnamese_benchmark_fixture_documents_selection_evidence():
    benchmark = json.loads(_read(BENCHMARK_PATH))

    assert benchmark["fixture_version"] == "vi-semantic-retrieval-v1"
    assert benchmark["encoder"]["version"] == ENCODER_VERSION
    assert benchmark["encoder"]["artifact_sha256"] == MODEL_SHA256
    assert benchmark["encoder"]["dimension"] == 384
    assert benchmark["encoder"]["license"] == "MIT"
    assert benchmark["method"]["similarity"] == "cosine"
    assert benchmark["method"]["query_prefix"] == "query: "
    assert benchmark["method"]["document_prefix"] == "passage: "

    documents = {item["id"] for item in benchmark["documents"]}
    queries = benchmark["queries"]
    assert len(documents) >= 8
    assert len(queries) >= 5
    assert all(query["relevant_document_ids"] for query in queries)
    assert all(
        set(query["relevant_document_ids"]) <= documents for query in queries
    )

    results = benchmark["results"]
    assert results["query_count"] == len(queries)
    assert results["recall_at_1"] >= 0.8
    assert results["mrr_at_10"] >= 0.8
    assert results["embedding_dimension_observed"] == 384
    assert results["all_embeddings_finite"] is True

    serialized = json.dumps(benchmark, ensure_ascii=False).lower()
    assert "user_id" not in serialized
    assert "post_id" not in serialized
    assert not re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        serialized,
    )


def test_runtime_sql_fixture_exercises_constraints_and_existing_post_fallback():
    fixture = _read(SQL_FIXTURE_PATH)
    normalized = " ".join(fixture.lower().split())

    for expected in (
        "wrong dimension",
        "unsupported encoder",
        "invalid content hash",
        "non-normalized topics",
        "duplicate feature",
        "immutable feature",
        "immutable encoder",
        "multiple encoder versions",
        "existing post without features",
        "future feature",
        "malformed encoder version",
        "uppercase encoder revision",
        "short encoder revision",
        "mismatched encoder identity",
        "direct feature delete",
        "parent post cascade",
    ):
        assert expected in normalized


def test_executable_postgres_migration_harness_is_committed():
    harness = _read(MIGRATION_HARNESS_PATH)

    assert MIGRATION_HARNESS_PATH.stat().st_mode & 0o111
    assert "postgres:18-trixie" in harness
    assert "20260831000019_post_content_features.sql" in harness
    assert "migration_contract.sql" in harness
    assert "existing post was not preserved" in harness
    assert "psql -v ON_ERROR_STOP=1" in harness
