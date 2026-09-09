"""Opt-in integration check; requires an isolated fully migrated PostgreSQL DB."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import asyncpg
import pytest

from app.db import fetch_user_history
from app.features import gather_candidates, candidates_semantic
from app.serving_context import load_author_context, load_nrms_records
from app.retrieval_telemetry import record_pool
from app.settings import Settings
from workers.nlp_worker.app.content_features import ENCODER_VERSION, content_hash


@pytest.mark.asyncio
async def test_real_postgres_nrms_queries_and_retention():
    url = os.getenv('MIND_TEST_DATABASE_URL')
    if not url:
        pytest.skip('set MIND_TEST_DATABASE_URL to an isolated migrated database')
    connection = await asyncpg.connect(url)
    transaction = connection.transaction()
    await transaction.start()
    try:
        viewer, author, post = uuid4(), uuid4(), uuid4()
        at = datetime.now(timezone.utc)
        for uid in [viewer, author]:
            await connection.execute('INSERT INTO users(id, username, email, password_hash) VALUES ($1,$2,$3,$4)',uid,'test_'+uid.hex[:12],uid.hex+'@test.local','unused-test-hash')
        content = 'Công nghệ Việt Nam phát triển hôm nay'
        await connection.execute("INSERT INTO posts(id, author_id, content, topics, status, created_at) VALUES ($1,$2,$3,ARRAY['tech'],'published',$4)",post,author,content,at-timedelta(days=2))
        vector = [1.]+[0.]*383
        await connection.execute('INSERT INTO post_content_features(post_id,encoder_version,content_hash,embedding,source_updated_at,computed_at) VALUES ($1,$2,$3,$4,$5,$6)',post,ENCODER_VERSION,content_hash(content),vector,at-timedelta(days=2),at-timedelta(days=1))
        await connection.execute('INSERT INTO follows VALUES ($1,$2,$3)', viewer,author,at-timedelta(days=1))
        await connection.execute("INSERT INTO behavior_events(client_event_id,user_id,post_id,event_type,metadata,occurred_at,ingested_at) VALUES ($1,$2,$3,'click','{\"event_version\":\"v2\"}',$4,$4)",uuid4(),viewer,post,at-timedelta(hours=1))
        db = SimpleNamespace(pool=connection)
        redis = SimpleNamespace(cli=SimpleNamespace(get=AsyncMock(return_value=None),setex=AsyncMock()))
        cfg = Settings(_env_file=None, candidate_telemetry_sample_rate=1)
        history = await fetch_user_history(db,redis,viewer,at=at,config=cfg)
        assert len(history.entries)==1
        context = await load_author_context(db,viewer,[author],at)
        assert context[author] == (True,1.)
        candidates = await gather_candidates(db,viewer,{'tech':1},6,seen_cooldown_days=7)
        assert [c.id for c in candidates] == [post]
        records = await load_nrms_records(db=db,redis=redis,user_id=viewer,candidates=candidates,observed_at=at,encoder_version=ENCODER_VERSION,dimension=384,config=cfg)
        assert len(records[0]['history']) == 1
        assert records[0]['article']['content_hash'] == content_hash(content)
        semantic = await candidates_semantic(db,redis,viewer,config=cfg,observed_at=at)
        assert semantic[0].id == post
        generation=uuid4()
        await record_pool(db,generation,candidates,model_version='test',sample_rate=1)
        await record_pool(db,generation,candidates,model_version='test',sample_rate=1)
        assert await connection.fetchval('SELECT count(*) FROM recommendation_candidate_events WHERE retrieval_request_id=$1',generation)==1
        # An immutable row rejects updates, while bounded expiry permits deletes.
        async with connection.transaction():
            with pytest.raises(asyncpg.ObjectNotInPrerequisiteStateError):
                await connection.execute("UPDATE recommendation_candidate_events SET source='changed' WHERE retrieval_request_id=$1",generation)
        await connection.execute("INSERT INTO recommendation_candidate_events(retrieval_request_id,post_id,stage,source,eligibility_reason,model_version,retrieval_version,recorded_at) VALUES ($1,$2,'eligible','recent','passed','test','test',$3)",uuid4(),post,at-timedelta(days=8))
        assert await connection.fetchval('SELECT prune_recommendation_candidate_events(7,10000)')==1
        assert await connection.fetchval('SELECT count(*) FROM recommendation_candidate_events WHERE retrieval_request_id=$1',generation)==1
    finally:
        await transaction.rollback()
        await connection.close()
