from pathlib import Path


def test_feature_event_receipts_are_durable_and_unique():
    root = Path(__file__).resolve().parents[3]
    migration = root / "migrations/20260827000015_feature_event_receipts.sql"
    sql = migration.read_text()

    assert "CREATE TABLE feature_event_receipts" in sql
    assert "event_id" in sql
    assert "PRIMARY KEY" in sql
    assert "processed_at" in sql
