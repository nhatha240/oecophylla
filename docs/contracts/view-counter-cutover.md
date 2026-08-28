# View counter cutover

`posts.view_count` must have exactly one writer during the recommendation
telemetry rollout:

- `LEGACY_VIEW_COUNTER_ENABLED=true` makes
  `POST /api/v1/posts/{id}/view` increment the counter.
- `BEHAVIOR_VIEW_COUNTER_ENABLED=true` makes qualified, idempotent behavior
  events increment the counter.
- Never enable both flags at the same time. Both default to `false` so a
  deployment cannot accidentally double count before an explicit cutover.

The legacy route remains available while disabled. It returns `204 No Content`
without changing the counter, so older clients do not fail during migration.

## Rollout

1. Deploy the behavior-event API with `BEHAVIOR_VIEW_COUNTER_ENABLED=false`.
2. Deploy the frontend telemetry tracker and verify accepted/duplicate/rejected
   behavior-event metrics and persisted `behavior_events` rows.
3. In one coordinated configuration rollout, set
   `LEGACY_VIEW_COUNTER_ENABLED=false` and
   `BEHAVIOR_VIEW_COUNTER_ENABLED=true`.
4. Monitor behavior-event duplicate rate, accepted view rate, and the change in
   `posts.view_count`. Do not use the approximate trending projection as the
   source of truth.

## Rollback

1. Set `BEHAVIOR_VIEW_COUNTER_ENABLED=false` and verify the interaction-service
   rollout has completed.
2. Only then set `LEGACY_VIEW_COUNTER_ENABLED=true`.

Do not disable behavior-event ingestion during this rollback. The append-only
log remains available for audit and rebuilding even while its counter writer is
disabled.
