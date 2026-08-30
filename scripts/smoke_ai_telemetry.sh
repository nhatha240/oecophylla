#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

legacy="${LEGACY_VIEW_COUNTER_ENABLED:-false}"
behavior="${BEHAVIOR_VIEW_COUNTER_ENABLED:-false}"
legacy_normalized="$(printf '%s' "$legacy" | tr '[:upper:]' '[:lower:]')"
behavior_normalized="$(printf '%s' "$behavior" | tr '[:upper:]' '[:lower:]')"
if [[ "$legacy_normalized" == "true" && "$behavior_normalized" == "true" ]]; then
  echo "LEGACY_VIEW_COUNTER_ENABLED and BEHAVIOR_VIEW_COUNTER_ENABLED must not both be true" >&2
  exit 1
fi

bash tests/test_recommendation_telemetry_contract.sh

# This proves rollback does not touch or require a model artifact.
(
  cd recommendation_api
  uv run --with-requirements requirements.txt python -c \
    'from pathlib import Path; from app.model_ranker import RankerRuntime; runtime = RankerRuntime.initialize("heuristic", Path("/missing")); assert runtime.predictor is None'
) >/dev/null
echo "rollback smoke passed: RANKER_MODE=heuristic does not load an artifact"

if [[ "${SKIP_DATABASE_TRACE:-false}" == "true" ]]; then
  echo "database trace skipped explicitly; release evidence remains INCONCLUSIVE"
  exit 0
fi

compose_command=(docker compose)
if [[ ! -f .env && -f .env.example ]]; then
  compose_command+=(--env-file .env.example)
fi

if ! "${compose_command[@]}" ps --status running --services | grep -qx postgres; then
  echo "postgres is not running; full trace is INCONCLUSIVE" >&2
  exit 2
fi

trace="$({
  "${compose_command[@]}" exec -T postgres \
    psql -U "${POSTGRES_USER:-oecophylla}" -d "${POSTGRES_DB:-oecophylla}" \
      -v ON_ERROR_STOP=1 -Atc "
        SELECT json_build_object(
          'request_id', impression.request_id,
          'impression_id', impression.id,
          'score', impression.score,
          'model_version', impression.model_version,
          'feature_snapshot', impression.feature_snapshot,
          'event_types', array_agg(DISTINCT event.event_type ORDER BY event.event_type)
        )
        FROM recommendation_impressions impression
        JOIN behavior_events event ON event.impression_id = impression.id
        WHERE event.event_type IN ('visible', 'view', 'dwell')
          AND impression.feature_snapshot ?& ARRAY[
            'schema_version',
            'topic_relevance',
            'freshness',
            'safety_score',
            'candidate_source',
            'is_followed_author',
            'author_affinity',
            'heuristic_score',
            'ml_score'
          ]
        GROUP BY impression.id
        HAVING bool_or(event.event_type = 'visible')
           AND bool_or(event.event_type = 'view')
           AND bool_or(event.event_type = 'dwell')
        ORDER BY max(event.occurred_at) DESC
        LIMIT 1;
      "
} 2>/dev/null)"

if [[ -z "$trace" ]]; then
  echo "no served -> visible/view/dwell trace exists; release evidence is INCONCLUSIVE" >&2
  exit 2
fi

echo "$trace"
echo "telemetry trace is dataset-eligible; generate the temporal dataset and verify its hashed request_group before release"
