from pathlib import Path


def test_preference_v2_migration_is_additive_versioned_and_canonical_backfill_ready():
    root = Path(__file__).resolve().parents[3]
    migration = root / "migrations/20260831000020_user_preference_vectors_v2.sql"
    sql = migration.read_text()

    assert "CREATE TABLE user_preference_vectors_v2" in sql
    assert "preference-vector-v2" in sql
    assert "positive_weights" in sql
    assert "negative_weights" in sql
    assert "reference_at" in sql
    assert "behavior_events" in sql
    assert "DROP TABLE" not in sql.upper()

