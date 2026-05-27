import pytest
from unittest.mock import AsyncMock
from app.kafka_consumer import _process_one


@pytest.mark.asyncio
async def test_idempotent_skips_post_with_existing_topics():
    """Re-invoking on a post that already has topics leaves it untouched."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"content": "AI and tech stuff", "topics": ["ai", "tech"]}

    envelope = {"data": {"post_id": "00000000-0000-0000-0000-000000000001"}}
    await _process_one(conn, envelope)

    # execute should NOT be called because topics already set
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_infers_and_updates_when_topics_empty():
    """Post with empty topics gets updated."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"content": "I love AI and machine learning", "topics": []}
    conn.execute.return_value = "UPDATE 1"

    envelope = {"data": {"post_id": "00000000-0000-0000-0000-000000000002"}}
    await _process_one(conn, envelope)

    conn.execute.assert_called_once()
    # First arg should be the UPDATE sql, second should be topics list, third uuid
    call_args = conn.execute.call_args[0]
    topics_arg = call_args[1]
    assert "ai" in topics_arg
