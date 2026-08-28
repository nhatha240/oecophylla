from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import features
from app.settings import Settings


VIEWER_ID = UUID("00000000-0000-0000-0000-000000000001")
POST_ID = UUID("00000000-0000-0000-0000-000000000010")
AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000020")


class RecordingPool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        self.calls.append((query, args))
        return [
            {
                "id": POST_ID,
                "author_id": AUTHOR_ID,
                "topics": ["ai"],
                "safety_score": 0.9,
                "created_at": datetime.now(timezone.utc),
            }
        ]


def db_with(pool: RecordingPool) -> SimpleNamespace:
    return SimpleNamespace(pool=pool)


def assert_shared_exclusion(query: str, args: tuple[object, ...]) -> None:
    sql = " ".join(query.lower().split())

    assert "join users" in sql
    assert "is_active = true" in sql
    assert "p.status = 'published'" in sql
    assert "i.type = 'hide'::interaction_type" in sql
    assert "r.reporter_id = $1" in sql
    assert "b.event_type in ('visible', 'view')" in sql
    assert "b.occurred_at >= now() - make_interval(days => $2)" in sql
    assert "$2 = 0" in sql
    assert "recommendation_impressions" not in sql
    assert args[0] == VIEWER_ID
    assert args[1] == 7

    # Exclusion is part of WHERE and therefore executes before the source limit.
    assert sql.index("not exists") < sql.rindex("limit")


@pytest.mark.asyncio
async def test_every_candidate_source_excludes_hide_report_and_recent_seen_before_limit():
    calls = [
        lambda db: features.candidates_from_followed(
            db, VIEWER_ID, limit=10, seen_cooldown_days=7
        ),
        lambda db: features.candidates_from_topics(
            db, VIEWER_ID, ["ai"], limit=10, seen_cooldown_days=7
        ),
        lambda db: features.candidates_recent(
            db, VIEWER_ID, limit=10, seen_cooldown_days=7
        ),
        lambda db: features.candidates_for_ids(
            db, VIEWER_ID, [POST_ID], "manual", seen_cooldown_days=7
        ),
    ]

    for call in calls:
        pool = RecordingPool()
        candidates = await call(db_with(pool))

        assert [candidate.id for candidate in candidates] == [POST_ID]
        assert len(pool.calls) == 1
        assert_shared_exclusion(*pool.calls[0])


@pytest.mark.asyncio
async def test_seen_cooldown_zero_disables_only_seen_filtering():
    pool = RecordingPool()

    await features.candidates_recent(
        db_with(pool), VIEWER_ID, limit=10, seen_cooldown_days=0
    )

    query, args = pool.calls[0]
    sql = " ".join(query.lower().split())
    assert args[:2] == (VIEWER_ID, 0)
    assert "$2 = 0" in sql
    assert "i.type = 'hide'::interaction_type" in sql
    assert "from reports r" in sql


@pytest.mark.asyncio
async def test_cold_start_still_uses_recent_candidates_with_user_scoped_exclusion():
    pool = RecordingPool()

    candidates = await features.gather_candidates(
        db_with(pool),
        VIEWER_ID,
        user_vec={},
        pool_size=6,
        seen_cooldown_days=7,
    )

    assert candidates
    recent_calls = [call for call in pool.calls if "JOIN follows" not in call[0]]
    assert recent_calls
    assert all(call[1][0] == VIEWER_ID for call in pool.calls)


def test_seen_cooldown_defaults_to_seven_days_and_accepts_zero(monkeypatch):
    monkeypatch.delenv("SEEN_COOLDOWN_DAYS", raising=False)
    assert Settings(_env_file=None).seen_cooldown_days == 7

    monkeypatch.setenv("SEEN_COOLDOWN_DAYS", "0")
    assert Settings(_env_file=None).seen_cooldown_days == 0


def test_candidate_metrics_are_defined_per_source_and_exclusion_reason():
    assert features.CANDIDATE_SOURCE_REQUESTS._labelnames == ("source",)
    assert features.CANDIDATE_SOURCE_RESULTS._labelnames == ("source",)
    assert features.CANDIDATE_EXCLUSIONS._labelnames == ("reason",)
