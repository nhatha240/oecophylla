#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
migration="$repo_root/migrations/20260827000013_recommendation_telemetry.sql"
contract="$repo_root/docs/contracts/recommendation-telemetry-v1.md"
fixture="$repo_root/tests/fixtures/recommendation_telemetry/schema_contract.sql"

fail() {
  echo "telemetry contract check failed: $1" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "missing ${1#"$repo_root/"}"
}

require_pattern() {
  local pattern="$1"
  local file="$2"
  local description="$3"
  grep -Eiq "$pattern" "$file" || fail "$description"
}

require_file "$migration"
require_file "$contract"
require_file "$fixture"

require_pattern 'CREATE[[:space:]]+TABLE[[:space:]]+recommendation_impressions' "$migration" \
  'migration must create recommendation_impressions'
require_pattern 'CREATE[[:space:]]+TABLE[[:space:]]+behavior_events' "$migration" \
  'migration must create behavior_events'
require_pattern 'UNIQUE[[:space:]]*\([[:space:]]*request_id[[:space:]]*,[[:space:]]*user_id[[:space:]]*,[[:space:]]*post_id[[:space:]]*\)' "$migration" \
  'impressions must reject duplicate request/user/post rows'
require_pattern 'client_event_id[[:space:]]+UUID[[:space:]]+NOT[[:space:]]+NULL[[:space:]]+UNIQUE' "$migration" \
  'behavior events must enforce client_event_id idempotency'
require_pattern 'feature_snapshot[[:space:]]+JSONB[[:space:]]+NOT[[:space:]]+NULL' "$migration" \
  'feature_snapshot must be required JSONB'
require_pattern 'dwell_ms.*1800000' "$migration" \
  'dwell_ms must be capped at 30 minutes'
require_pattern 'ON[[:space:]]+DELETE[[:space:]]+CASCADE' "$migration" \
  'user/post deletion behavior must be explicit'
require_pattern 'idx_recommendation_impressions_user_served' "$migration" \
  'missing user/time impression index'
require_pattern 'idx_behavior_events_user_occurred' "$migration" \
  'missing user/time behavior index'

require_pattern 'user_id.*JWT' "$contract" \
  'contract must require server-derived user_id from JWT'
require_pattern 'client_event_id' "$contract" \
  'contract must document idempotency'
require_pattern 'rank-features-v1' "$contract" \
  'contract must version the feature snapshot'
require_pattern 'visible.*không.*positive|visible.*not.*positive' "$contract" \
  'contract must state that visible is not a positive label'
require_pattern 'forward migration|migration mới' "$contract" \
  'contract must document forward-only rollback policy'

require_pattern 'BEGIN;' "$fixture" 'fixture must run transactionally'
require_pattern 'ROLLBACK;' "$fixture" 'fixture must roll back all test data'
require_pattern 'duplicate client_event_id' "$fixture" \
  'fixture must exercise client event idempotency'
require_pattern 'cross-user impression' "$fixture" \
  'fixture must reject cross-user impression attachment'

echo "telemetry contract static checks passed"
