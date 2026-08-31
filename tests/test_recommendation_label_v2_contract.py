from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
CONTRACT_PATH = REPO_ROOT / "docs/contracts/recommendation-label-v2.json"
DOCUMENT_PATH = REPO_ROOT / "docs/contracts/recommendation-label-v2.md"
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/recommendation_telemetry/label-v2-cases.json"
)

EXPECTED_SEMANTICS = {
    "exposure",
    "click",
    "qualified_read",
    "positive",
    "strong_positive",
    "negative",
    "strong_negative",
}
EXPECTED_CASES = {
    "exactly_at_qualified_read_threshold",
    "below_qualified_read_threshold",
    "click_before_visible",
    "long_dwell",
    "like",
    "comment",
    "save",
    "share",
    "hide",
    "report",
    "unlike_reverses_like",
    "unsave_reverses_save",
    "unshare_reverses_share",
    "unhide_reverses_hide",
    "duplicate_event",
}
EXPECTED_ORDERING_CASES = {
    "occurred_at_orders_reversal",
    "ingested_at_breaks_occurred_at_tie",
    "event_id_breaks_timestamp_tie",
}


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_contract_is_versioned_and_defines_rollout_controls():
    contract = _load_json(CONTRACT_PATH)

    assert "$schema" not in contract
    assert contract["contract_version"] == "engagement-label-v2"
    assert contract["label_version"] == "v2"
    assert set(contract["semantics"]) == EXPECTED_SEMANTICS

    flags = contract["rollout_flags"]
    assert flags["RECOMMENDATION_LABEL_VERSION"]["allowed"] == ["v1", "v2"]
    assert flags["FEATURE_EVENT_VERSION"]["allowed"] == ["v1", "v2"]
    assert flags["QUALIFIED_READ_MS"]["type"] == "positive_integer"
    assert flags["QUALIFIED_READ_MS"]["default"] == 10_000

    threshold = contract["thresholds"]["qualified_read_ms"]
    assert threshold["flag"] == "QUALIFIED_READ_MS"
    assert threshold["comparison"] == ">="
    assert threshold["unit"] == "milliseconds"


def test_contract_defines_required_fields_events_precedence_and_reversals():
    contract = _load_json(CONTRACT_PATH)

    required_fields = contract["required_fields"]
    required = set(required_fields["all_events"])
    assert {
        "event_id",
        "event_version",
        "event_type",
        "user_id",
        "post_id",
        "occurred_at",
        "ingested_at",
    } <= required
    assert "request_id" not in required
    request_context = required_fields["recommendation_context"]
    assert request_context["field"] == "request_id"
    assert request_context["nullable"] is True
    assert request_context["when_present"] == "server_verified"
    assert "direct_entry" in request_context["nullable_for"]
    assert "canonical_action_without_recommendation_context" in request_context[
        "nullable_for"
    ]
    assert contract["required_fields"]["by_event"]["visible"] == [
        "viewport_ratio"
    ]
    assert contract["required_fields"]["by_event"]["view"] == [
        "continuous_visible_ms"
    ]
    assert contract["required_fields"]["by_event"]["dwell"] == ["dwell_ms"]

    events = contract["events"]
    assert events["visible"]["semantic"] == "exposure"
    assert events["click"]["semantic"] == "click"
    assert events["view"]["semantic"] == "qualified_read"
    assert events["dwell"]["semantic"] == "qualified_read"
    assert events["like"]["semantic"] == "positive"
    assert events["comment"]["semantic"] == "positive"
    assert events["save"]["semantic"] == "strong_positive"
    assert events["share"]["semantic"] == "strong_positive"
    assert events["hide"]["semantic"] == "strong_negative"
    assert events["report"]["semantic"] == "strong_negative"
    assert events["implicit_skip"]["semantic"] == "negative"

    for undo in ("unlike", "unsave", "unshare", "unhide"):
        assert "semantic" not in events[undo]
        assert events[undo]["kind"] == "state_transition_reversal"

    reversals = contract["reversals"]
    assert reversals == {
        "unlike": "like",
        "unsave": "save",
        "unshare": "share",
        "unhide": "hide",
    }
    precedence = contract["precedence"]
    assert precedence[0] == "strong_negative"
    assert precedence[-1] == "exposure"
    assert set(precedence) == EXPECTED_SEMANTICS

    deduplication = contract["event_deduplication"]
    assert deduplication["identity_field"] == "event_id"
    assert deduplication["identical_duplicate"] == "ignore_success"
    assert deduplication["conflicting_duplicate"] == "reject"

    assert contract["resolution"]["ordering"] == [
        "occurred_at",
        "ingested_at",
        "event_id",
    ]


def test_contract_defines_private_request_identity_and_collision_policy():
    contract = _load_json(CONTRACT_PATH)
    identity = contract["request_identity"]

    assert identity["online"]["fields"] == ["user_id", "request_id"]
    assert identity["offline"]["expression"] == "H(salt:user_id:request_id)"
    assert identity["offline"]["algorithm"] == "HMAC-SHA-256"
    assert identity["offline"]["key_source"] == "configured hash_salt secret"
    assert identity["offline"]["key_scope"] == "dataset_version"
    assert identity["offline"]["hash_salt_is_hmac_key"] is True
    assert identity["offline"]["hash_salt_is_message_data"] is False
    assert identity["offline"]["raw_identity_exported"] is False

    fingerprint = identity["request_fingerprint"]
    assert fingerprint["immutable"] is True
    assert fingerprint["request_metadata_fields"] == [
        "feed_source",
        "model_version",
        "feature_schema_version",
    ]
    assert fingerprint["ordered_candidate_fields"] == ["position", "post_id"]
    assert fingerprint["algorithm"] == "SHA-256"

    policy = identity["collision_policy"]
    assert policy["different_request_fingerprint"] == "reject_request"
    assert policy["duplicate_position"] == "reject_request"
    assert policy["duplicate_post_id"] == "reject_request"
    assert policy["identical_candidate_retry"] == "deduplicate_success"
    assert policy["conflicting_candidate_retry"] == "reject_request"


def test_fixture_covers_required_label_and_retry_scenarios():
    contract = _load_json(CONTRACT_PATH)
    fixture = _load_json(FIXTURE_PATH)

    assert fixture["contract_version"] == contract["contract_version"]
    assert fixture["qualified_read_ms"] == contract["rollout_flags"][
        "QUALIFIED_READ_MS"
    ]["default"]

    cases = {case["id"]: case for case in fixture["label_cases"]}
    assert EXPECTED_CASES <= set(cases)
    assert cases["exactly_at_qualified_read_threshold"]["expected"][
        "semantic"
    ] == "qualified_read"
    assert cases["below_qualified_read_threshold"]["expected"][
        "semantic"
    ] == "negative"
    assert cases["click_before_visible"]["expected"]["semantic"] == "click"
    assert cases["comment"]["expected"]["semantic"] == "positive"
    assert cases["duplicate_event"]["expected"]["deduplicated_events"] == 1

    for case in cases.values():
        assert case["events"], case["id"]
        assert case["expected"]["semantic"] in EXPECTED_SEMANTICS

    retry_cases = {case["id"]: case for case in fixture["request_retry_cases"]}
    assert retry_cases["identical_candidate_retry"]["expected"] == (
        "deduplicate_success"
    )
    assert retry_cases["different_request_fingerprint"]["expected"] == (
        "reject_request"
    )
    assert retry_cases["duplicate_position"]["expected"] == "reject_request"
    assert retry_cases["duplicate_post_id"]["expected"] == "reject_request"
    assert retry_cases["conflicting_candidate_retry_payload"]["expected"] == (
        "reject_request"
    )

    event_retry_cases = {
        case["id"]: case for case in fixture["event_retry_cases"]
    }
    assert event_retry_cases["conflicting_duplicate_event_id"]["expected"] == (
        "reject"
    )

    ordering_cases = {case["id"]: case for case in fixture["ordering_cases"]}
    assert set(ordering_cases) == EXPECTED_ORDERING_CASES
    for case in ordering_cases.values():
        assert case["input_events"] != case["expected"]["processing_order"]
        assert case["expected"]["semantic"] in EXPECTED_SEMANTICS
        assert len(case["expected"]["processing_order"]) == len(
            case["input_events"]
        )


def test_human_contract_documents_compatibility_and_rollout_safety():
    document = DOCUMENT_PATH.read_text(encoding="utf-8")

    assert "engagement-label-v2" in document
    assert "H(salt:user_id:request_id)" in document
    assert "RECOMMENDATION_LABEL_VERSION" in document
    assert "FEATURE_EVENT_VERSION" in document
    assert "QUALIFIED_READ_MS" in document
    assert "hash_salt" in document
    assert "hmac key" in document.lower()
    assert "direct-entry" in document.lower()
    assert "state-transition reversal" in document.lower()
    assert "không được trộn" in document.lower()
    assert "v1" in document and "v2" in document
