import json
from pathlib import Path
import pytest
from ai_pipeline.schemas import Impression, BehaviorEvent


def test_postgres_jsonb_text_decodes_like_fixture_objects():
    payload = json.loads((Path(__file__).parent/'fixtures/telemetry_v1.json').read_text())
    source = payload['impressions'][0]
    encoded = dict(source, feature_snapshot=json.dumps(source['feature_snapshot']))
    assert Impression.from_mapping(encoded) == Impression.from_mapping(source)
    event = dict(payload['events'][0], metadata=json.dumps({'event_version':'v2'}))
    parsed = BehaviorEvent.from_mapping(event)
    assert parsed.event_version == 'v2'
    assert parsed.metadata == {'event_version':'v2'}


@pytest.mark.parametrize('value', ['[]','null','false','"invalid"'])
def test_postgres_feature_snapshot_requires_json_object(value):
    payload = json.loads((Path(__file__).parent/'fixtures/telemetry_v1.json').read_text())
    with pytest.raises(ValueError):
        Impression.from_mapping(dict(payload['impressions'][0],feature_snapshot=value))
