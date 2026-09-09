from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.ranking import build_rank_feature_snapshot
from app.schemas import CandidatePost


def test_snapshot_freshness_is_reproducible_at_its_observation_time():
    observed = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    candidate = CandidatePost(id=uuid4(), author_id=uuid4(), topics=[], safety_score=1.0, created_at=observed, source="recent")
    snapshot = build_rank_feature_snapshot({}, candidate, observed_at=observed)
    assert snapshot.freshness == pytest.approx(1.0)
    assert snapshot.preference_observed_at == observed
