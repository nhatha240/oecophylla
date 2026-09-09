# Project review and phase/task status

Reviewed 2026-09-08 against the working checkout on `codex/review-fixes-20260908`,
starting at `ea9c51b`. This checkout contains pre-existing uncommitted feature work.
Statuses below distinguish merged implementation, local verification, and release evidence.
Finalized 2026-09-09; the test results below were captured during the 2026-09-08 run.

## Review fixes

| Finding | Result | Regression evidence |
|---|---|---|
| Server API fetch throws on undefined variables | Fixed; GET/HEAD have no body, write requests preserve bytes | `frontend/src/hooks.server.test.ts`: 7 cases; 6 failed before the fix |
| Inactive accounts obtain new sessions | Fixed; email/username login, refresh, and `/auth/me` reject inactive rows | `auth-service/tests/review_regressions.rs`: all four requests changed from 200 to 401 |
| Direct URLs expose unpublished posts | Fixed; published posts stay public; pending/hidden/flagged posts require owner/admin | `content-service/tests/review_regressions.rs`: 16 status/viewer combinations |
| Profile save rejects uploaded avatar URL | Fixed; accepts the same user's currently stored upload URL and validated HTTPS URLs | `user-service/tests/review_regressions.rs`: upload/read/save succeeds; arbitrary local and unsafe URLs rejected |

The backend regressions execute the current handlers over HTTP with real PostgreSQL 18
and Redis in isolated test containers. They apply the repository migrations; they do
not use production credentials or the existing application database.

## Verification

| Check | Result |
|---|---|
| Rust workspace library/binary unit tests | 70 passed; existing dead-code warnings remain |
| Three backend review integration targets | 15 passed, including 3 new HTTP/database regressions and 12 included module tests |
| Frontend unit tests | 60 passed |
| Svelte check | 0 errors, 0 warnings |
| Frontend production build | Passed |
| Chromium browser regression | 1 passed: authenticated settings → avatar upload → profile save → reload, against freshly built local auth/user services and isolated PostgreSQL/Redis |
| Frontend ESLint | 0 errors, 9 existing warnings |
| Offline AI pipeline | 83 passed, including request-group/timestamp ties, private identities, and future-history/feature guards |
| Recommendation API (preceding review, same implementation) | 71 passed, 2 deprecation warnings |
| Feature worker (preceding review, same implementation) | 36 passed |

Run the new database regressions with explicit isolated service URLs:

```bash
cd backend
REVIEW_DATABASE_URL="$TEST_DATABASE_URL" REVIEW_REDIS_URL="$TEST_REDIS_URL" \
  cargo test -p auth-service -p content-service -p user-service \
  --test review_regressions --no-fail-fast
```

Frontend checks: `npm run check`, `npm test`, `npm run lint`, `npm run build` from
`frontend/`. The browser regression is `e2e/review-fixes.spec.ts`.
Its review run used a temporary local HTTP gateway for auth/user/content only;
it does not establish full Envoy/feed/Kafka end-to-end acceptance.

The RED checkpoint is `01e27b4`. Content/user handler fixes overlap pre-existing
uncommitted feature changes and remain in the working checkout to preserve that work.
The GREEN checkpoint records the independently isolatable auth/hook fixes, browser
regression, and this evidence. Validate the complete working checkout, not just a
cherry-pick of these checkpoints onto a clean branch.

## Product phases

| Phase | Evidence in Git/current source | Completion interpretation |
|---|---|---|
| 0–1: infrastructure, identity, content, frontend | `phase-0-1-complete` tag | Historical milestone; current identity/content fixes verified above |
| 2A: interactions, comments, reports | `phase-2a-complete` tag | Historical milestone; full phase smoke not rerun in this review |
| 2B: feed, recommendation, workers | `phase-2b-complete` tag | Historical milestone; not proof of an ML production release |
| 3: moderation, notifications, NLP | `phase-3-complete` tag | Historical milestone; direct-post visibility and inactive login corrected here |
| 4: analytics, evaluation, observability | Services and evaluation code present; no `phase-4-complete` tag | Implemented in parts; no fresh full-phase acceptance claim |

The August user/post report is historical evidence, not a current blanket 13/13
acceptance result. New regressions found after that report are recorded above.

## MIND-aligned tasks

Source: [completion plan](../plans/oecophylla-mind-aligned-recommendation-completion.md).
“Merged” below describes implementation history, not satisfaction of every live release gate.

| Task | Current status | Evidence / remaining work |
|---|---|---|
| T1a label contract | Merged | Shared JSON contract and fixtures in `docs/contracts/` and `tests/fixtures/` |
| T1b label implementation | Merged | Shared label semantics across browser/Rust/Python; versioned feature events |
| T2 grouped splits/MIND metrics | Merged; offline suite green | Atomic request groups and tied timestamps, AUC/MRR/nDCG tests |
| T3 preference vector v2 | Merged | Decay/backfill/versioned-cache implementation; worker tests pass |
| T4a content feature contract | Merged | Additive feature/encoder schema and provenance contract |
| T4b embedding worker | Merged | Idempotency, fallback, rebuild code; actual model inference not rerun here |
| T5 temporal histories | Merged; offline/API suites green | Prior-only history and versioned cache loaders |
| T6 dataset v2/MIND adapter | Merged at `ea9c51b`; offline suite green | Local/MIND fixtures, identity and provenance validation, unsplit timestamp buckets |
| T7 NRMS model | Open on this branch | Work exists on `codex/t7-nrms-hardening`, not merged here; its inspected head `a54d381` is a serving-snapshot RED checkpoint |
| T8a NRMS shadow serving | Open | Current branch loads sklearn artifacts; generic LR shadow mode does not satisfy NRMS serving criteria |
| T8b retrieval telemetry | Open | Candidate backfill, semantic retrieval, and candidate-stage traceability still need completion evidence |
| T9 release gate | Open / INCONCLUSIVE | Requires production-domain Vietnamese holdout, live served→behavior→dataset→shadow trace, segments, shadow window/canary, rollback evidence |

## Earlier logging/ML plan

Source: [logging and ML execution plan](AI_USER_LOGGING_AND_ML_EXECUTION_PLAN.md).
These IDs differ from the later MIND task IDs.

| Tasks | Implementation evidence | Acceptance status |
|---|---|---|
| P0-T1 / P0-T2 | Telemetry schema and rank-feature contracts | Present; deployment-specific acceptance not rerun |
| P1-T1 / P1-T2 / P1-T3 | Served impressions, append-only behavior API, browser telemetry | Code/tests present; complete live trace pending |
| P1-T4 / P1-T5 | Event idempotency and view-counter cutover flags | Code/tests present; monitored cutover not established by this review |
| P2-T1 | Metric library and temporal evaluation | Offline/API tests pass |
| P3-T1 | Hide/report/seen exclusion | API tests pass; full fallback journey not rerun |
| P4-T1 | NLP and feature versioning | Incomplete: ordinary post create/update still accepts client-supplied `topics`, contrary to the server-owned-topic exit criterion |
| P5-T1 / P5-T2 | Dataset generation and LR model/artifact pipeline | Offline suite passes; real dataset/holdout acceptance remains separate |
| P6-T1 | LR ML/shadow modes and evaluator | Code/tests present; production comparison remains inconclusive |
| P7-T1 | Retention, alerts, dashboards, release document | Incomplete: live trace, rollback rehearsal, production holdout, and account-erasure behavior need evidence |

## Remaining limits

- Keep `RANKER_MODE=heuristic`. Passing these regressions does not approve ML promotion.
- Account deletion currently sets `is_active=false`; it does not physically delete the
  user row and therefore does not trigger foreign-key erasure cascades. Raw telemetry
  remains subject to retention. Do not describe this endpoint as completed data erasure.
- Existing access JWTs in services that only check signatures remain valid until expiry;
  this change closes new login/refresh and `/auth/me` for inactive users, not system-wide
  immediate access-token revocation.
- Existing deployed containers were not rebuilt/replaced by this review. Ship the fixed
  services and frontend together, with the avatar migration already applied.
- No repository-wide coverage percentage or fresh production ML quality claim is made.
