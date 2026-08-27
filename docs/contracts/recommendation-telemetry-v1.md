# Recommendation telemetry contract v1

**Contract version:** `recommendation-telemetry-v1`  
**Feature schema:** `rank-features-v1`  
**Owner:** recommendation/feed/interaction pipeline  
**Migration:** `20260827000013_recommendation_telemetry.sql`  

## 1. Purpose

This contract defines the append-only data needed to train and evaluate Oecophylla's recommendation system without treating aggregate counters or mutable interaction state as historical truth.

User journeys covered by the contract:

1. As an authenticated user, each feed item served to me is linked to the model and feature values that ranked it.
2. As an authenticated user, visible, qualified-view, click and dwell telemetry is attached to my server-verified identity without accepting `user_id` from the browser.
3. As a model developer, I can distinguish served items from actually visible exposures and can build time-split datasets without future-feature leakage.
4. As a privacy operator, deleting a user or post removes its directly identifying telemetry.

## 2. Trust boundaries

- `user_id` is always derived from the verified JWT/cookie by the server. The API must reject or ignore a client-supplied `user_id`.
- `model_version`, rank score, feed source, candidate source and feature snapshot are server-generated.
- The client telemetry endpoint may submit only `visible`, `view`, `click` and `dwell`.
- `like`, `unlike`, `save`, `unsave`, `share`, `unshare`, `hide`, `unhide`, `report` and `comment` are mirrored by their canonical server endpoints. The telemetry endpoint must reject client attempts to declare these labels directly.
- Never store raw JWTs, cookies, email addresses, IP addresses, device fingerprints or full comment text in telemetry.

## 3. Impression semantics

`recommendation_impressions` records items returned by the server after post hydration. It is a served log, not proof that the user saw the item.

- One feed response has one `request_id`.
- Each returned post has one impression and a zero-based `position`.
- `(request_id, user_id, post_id)` is unique.
- A cache hit creates new impressions because it is a new delivery to a user.
- A post removed during hydration must not receive an impression.
- `feed_source` describes the response path: for example `personalized`, `cache`, `fallback`, `following` or `trending`.
- `candidate_source` describes retrieval: for example `follow`, `topic`, `recent` or `trending`.
- `model_version` is the ranker that produced the returned order. Examples: `heuristic-v1`, `logreg-20260827-001`.
- Impression persistence is fail-open for feed availability. If batch persistence fails, the API returns `impression_id = null`, logs a structured error and increments a failure metric.

## 4. Behavior semantics

`behavior_events` is append-only. Unlike/save state changes never erase prior events.

| Event | Producer | Meaning | Positive label by itself? |
|---|---|---|---|
| `visible` | browser telemetry | At least 50% visible continuously for at least 800 ms | No |
| `view` | browser telemetry | At least 50% visible for at least 5 seconds, or the detail page was opened | Only with the dwell/action guardrail |
| `click` | browser telemetry | User deliberately opened the post from a feed | Yes, weak |
| `dwell` | browser telemetry | Aggregated reading duration; not emitted for every timer tick | Only when `dwell_ms >= 10000` |
| `like/unlike` | canonical like endpoint | State transition occurred | Like is positive; unlike reverses it |
| `save/unsave` | canonical save endpoint | State transition occurred | Save is strong positive; unsave reverses it |
| `share/unshare` | canonical share endpoint | State transition occurred | Share is strong positive; unshare reverses it |
| `hide/unhide` | canonical hide endpoint | State transition occurred | Hide is strong negative |
| `report` | canonical report endpoint | A valid report was created | Strong negative |
| `comment` | canonical comment endpoint | A valid comment was created | Positive |

Important label rule: `visible` is an exposure, not a positive label. The frontend must not emit `visible` and positive `view` from the same threshold.

## 5. Feature snapshot v1

`feature_snapshot` is captured at serving time. Training must not rebuild historical rows from current post counters.

```json
{
  "schema_version": "rank-features-v1",
  "topic_relevance": 0.75,
  "freshness": 0.8,
  "safety_score": 1.0,
  "candidate_source": "topic",
  "is_followed_author": false,
  "author_affinity": null,
  "heuristic_score": 0.625,
  "ml_score": null
}
```

Rules:

- `schema_version` is required and non-empty.
- Missing/unavailable features use JSON `null`, not a fabricated zero.
- Snapshot size is capped at 16 KiB by the database.
- Metadata that changes after serving must not be joined back as a historical feature.
- A trainer must reject unknown/incompatible feature schema versions unless an explicit adapter exists.

P0-T1 stores the versioned JSON object. P0-T2 defines the typed Python/Rust network representation and calculates the values in recommendation-api.

## 6. Idempotency and linkage

- Every behavior event has a `client_event_id UUID NOT NULL UNIQUE`.
- Browser retries retain the same `client_event_id`.
- Canonical server actions generate a stable event ID only when a state transition succeeds.
- Duplicate event IDs are treated as successful duplicates, not new behavior.
- If `impression_id` is present, the composite foreign key guarantees it belongs to the same `(user_id, post_id)`.
- Events without an impression remain valid for direct-entry detail views.
- `session_id` is a random UUID stored in browser `sessionStorage`; it is not a fingerprint.

## 7. Time handling

- `ingested_at` is authoritative server time.
- Client `occurred_at` is accepted only after server validation.
- Application validation clamps `occurred_at` to no earlier than 24 hours before `ingested_at` and no later than 5 minutes after it.
- Dataset label windows use validated `occurred_at`, with `ingested_at` retained for audit and late-arrival analysis.
- Only impressions whose label window has fully elapsed may become finalized training samples.

## 8. API limits and metadata allowlist

- Maximum batch size: 100 events.
- Maximum `dwell_ms`: 1,800,000 ms (30 minutes).
- Behavior `metadata` must be a JSON object of at most 8 KiB.
- Impression `feature_snapshot` must be a JSON object of at most 16 KiB.
- Unknown metadata keys are rejected until added to this contract.

Allowed metadata v1:

| Event | Keys |
|---|---|
| `visible` | `viewport_ratio` |
| `view` | `continuous_visible_ms`, `trigger` (`feed` or `detail`) |
| `click` | `target` (`post_detail`) |
| `dwell` | `trigger` (`viewport_exit`, `page_hidden`, `destroy`) |
| canonical actions | `source` only; no raw content |

## 9. Deletion, retention and privacy

- Deleting a user cascades to their impressions and behavior events.
- Deleting a post cascades to telemetry for that post.
- Deleting an impression alone sets only `behavior_events.impression_id` to null; the underlying event remains linked to its user/post.
- Raw telemetry retention target is 180 days. P7 implements and verifies the retention job; no deletion job is included in P0-T1.
- Longer-lived analytics must be aggregated/anonymized and must not contain raw user IDs.

## 10. Index/query contract

Required access paths:

- User impression history: `(user_id, served_at DESC)`.
- Post impression history: `(post_id, served_at DESC)`.
- Model evaluation window: `(model_version, served_at DESC)`.
- User behavior history: `(user_id, occurred_at DESC)`.
- Post behavior history: `(post_id, occurred_at DESC)`.
- Impression-to-events join: partial index on non-null `impression_id`.
- Event/time analysis: `(event_type, occurred_at DESC)`.

Indexes are created normally in this migration because both tables are new and empty. Future indexes on populated telemetry tables must use a non-blocking/forward migration strategy.

## 11. Migration and rollback policy

This schema is additive and forward-only in production.

- Do not edit migration 13 after it has been applied.
- Do not drop populated telemetry tables to roll back application code.
- Disable writers/readers through feature flags when necessary.
- Any schema correction uses a migration mới (a new forward migration).
- A destructive down migration is intentionally not supplied because it would erase training/audit data.

## 12. Verification

Static contract check:

```bash
bash tests/test_recommendation_telemetry_contract.sh
```

PostgreSQL fixture check against a disposable database after migrations:

```bash
docker compose --env-file .env.example \
  -f compose.yaml -f compose.dev.yaml up -d postgres migrate

docker compose --env-file .env.example \
  -f compose.yaml -f compose.dev.yaml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U oecophylla -d oecophylla \
  < tests/fixtures/recommendation_telemetry/schema_contract.sql
```

The fixture validates the valid served/visible/dwell/action sequence, JSON round-trip, idempotency, cross-user attachment rejection, boundary checks and user-deletion cascade. It runs inside a transaction and finishes with `ROLLBACK`.
