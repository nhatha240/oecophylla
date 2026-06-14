# Oecophylla — Admin Management Console Design

> Status: approved design (2026-06-14). Builds on Phase 3 moderation/admin work.
> Spec → plan → implementation. The recommendation-algorithm findings reviewed
> alongside this work are tracked separately (see §12), not in scope here.

## 1. Goals & non-goals

### 1.1 Goals

- Complete the admin console into a **full moderation + administration surface**:
  user management, a metrics dashboard, and report-queue polish — on top of the
  already-shipped Reports queue and Audit log.
- Give admins real account-level controls: **ban**, **temporary suspend**
  (auto-expiry), **reactivate**, and **role change** (`user ↔ creator ↔ admin`).
- Make account status **actually enforced** at authentication — today `is_active`
  is written but never checked, so a "ban" is cosmetic.
- Every state-changing admin action is audit-logged in the same DB transaction
  (coding rule #5).

### 1.2 Non-goals

- No recommendation-algorithm changes (the `diversity_weight`, dead `w4` term,
  trending/similarity retrieval, and half-life findings are out of scope — §12).
- No new analytics pipeline. The Metrics tab renders the **existing**
  `/admin/metrics` (and optionally reads analytics-service); we do not build new
  aggregation.
- No email/push notification to banned users. In-app status + login rejection
  message only.
- No appeals workflow, no IP/device bans, no rate-of-moderation analytics.

## 2. Brainstorm decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Full console: user mgmt + metrics + report-queue polish | User selected "Full console" |
| User actions | Ban + temporary suspend + reactivate + role change | User selected most-powerful set |
| Endpoint placement | **moderation-service** (`:8006`) | Already owns all `/admin/*`, writes `audit_logs` in-transaction, already mutates `users`; envoy routes `/admin/*` → `moderation_cluster` |
| Enforcement | Check at **login + refresh**, and **revoke refresh sessions** on ban/suspend | Banned users can't get new tokens; current 15-min access token lapses quickly. Avoids a per-request DB/Redis hit on the hot path |
| Status model | Derived from `is_active` + `suspended_until` | No new status enum; minimal migration |

## 3. Architecture & topology delta

No new services or containers. Changes are additive within three existing units:

- **moderation-service (`:8006`)** — owns the new `/admin/users` read + the
  `/admin/users/{id}/status` mutation. Already admin-guarded and audit-aware.
- **auth-service (`:8001`)** — gains active/suspended enforcement on login &
  refresh, and a helper to revoke a user's refresh sessions.
- **frontend (`/admin`)** — two new tabs (Users, Metrics) + report-queue polish.

Envoy needs **no new cluster**; `/admin/*` already maps to `moderation_cluster`.
Confirm the new sub-paths (`/admin/users`, `/admin/users/{id}/status`) match the
existing `/admin` prefix route (they do — prefix match).

### 3.1 Component responsibilities

| Unit | New responsibility |
|---|---|
| `moderation-service/repo.rs` | `list_users` (search/filter/cursor), `set_user_status` (mutate + audit in one tx), refresh-session revocation call |
| `moderation-service/handlers.rs` | `list_users`, `set_user_status` handlers (admin-guarded) |
| `auth-service` (login/refresh) | Reject banned/suspended users with 403 + reason |
| `auth-service/repo.rs` | `is_account_usable(user) -> Result` helper; `revoke_refresh_sessions(user_id)` |
| frontend `lib/api.ts` | `getAdminUsers`, `setUserStatus` |
| frontend components | `AdminUsersTable`, `AdminMetricsPanel`, `UserStatusDialog` |

## 4. Data model delta

### 4.1 Migration 14: `20260614000014_user_suspension.sql`

```sql
ALTER TABLE users ADD COLUMN suspended_until TIMESTAMPTZ NULL;
-- Optional: partial index to find currently-suspended accounts cheaply.
CREATE INDEX idx_users_suspended ON users(suspended_until)
  WHERE suspended_until IS NOT NULL;
```

Derived status (computed in query / DTO, no stored column):

| Status | Condition |
|---|---|
| `banned` | `is_active = false` |
| `suspended` | `is_active = true AND suspended_until > now()` |
| `active` | `is_active = true AND (suspended_until IS NULL OR suspended_until <= now())` |

`role` already exists (`user_role` enum: `user`/`creator`/`admin`). No enum change.

## 5. Redis keys

Reuses the existing refresh-session pattern. On ban/suspend, moderation-service
(or an auth-service call it triggers) deletes the user's refresh sessions:

| Key pattern | Action |
|---|---|
| `session:refresh:{token_hash}` | Deleted for the target user on ban/suspend so no new access token can be minted |

> Implementation note: refresh sessions are keyed by token hash, not user id.
> We need a reverse lookup. Add a per-user set `session:refresh:user:{user_id}`
> (members = token hashes) maintained at login/refresh, so revocation is one
> `SMEMBERS` + pipeline `DEL`. If a reverse index already exists, reuse it;
> verify during implementation.

## 6. Service endpoints

### 6.1 `moderation-service` (:8006)

```
GET  /admin/users
       ?q=<username|email substring>
       &status=active|suspended|banned|all   (default all)
       &role=user|creator|admin|all          (default all)
       &cursor=<opaque>&limit=<1..50>
     → { items: AdminUser[], next_cursor: string|null }     [JWT: admin]

PUT  /admin/users/{id}/status                                [JWT: admin]
     body (one of):
       { action: "ban",        reason: string }
       { action: "suspend",    reason: string, suspended_until: RFC3339 }
       { action: "reactivate", reason: string }
       { action: "set_role",   reason: string, role: "user"|"creator"|"admin" }
     → AdminUser (updated)
```

`AdminUser` DTO: `{ id, username, email, role, status, is_active,
suspended_until, created_at }`.

**Transaction & audit:** every mutation runs in one DB transaction that (a)
updates `users` and (b) inserts an `audit_logs` row
(`actor_id` = admin, `action` ∈ `USER_BANNED|USER_SUSPENDED|USER_REACTIVATED|USER_ROLE_CHANGED`,
`target_id` = user, `target_type` = `'user'`, `reason`, `metadata` =
`{ suspended_until?, old_role?, new_role? }`). On `ban`/`suspend`, after commit,
revoke the target's refresh sessions.

**Guards (return 409/422 with error envelope):**
- Admin cannot ban/suspend/demote **themselves**.
- Cannot demote the **last remaining admin** (`set_role` away from `admin` when
  they are the only active admin).
- `suspend` requires `suspended_until` strictly in the future.
- `set_role` to the user's current role is a no-op success.

### 6.2 `auth-service` (:8001) enforcement

- **Login** and **refresh**: after credential/token validation, reject if the
  account is not usable:
  - `is_active = false` → `403 { error: { code: "ACCOUNT_BANNED", message } }`
  - `suspended_until > now()` → `403 { error: { code: "ACCOUNT_SUSPENDED",
    message: "...until <ts>" } }`
- On successful login/refresh, register the issued refresh token hash in
  `session:refresh:user:{user_id}` so it can be revoked later.

### 6.3 Envoy

No change — `/admin/*` already routes to `moderation_cluster`. Verify the prefix
match covers `/admin/users` and `/admin/users/{id}/status` (it does).

## 7. Frontend changes

### 7.1 Admin console tabs

`/admin/+page.svelte` gains two tabs beside Reports & Audit: **Users**, **Metrics**.
`+page.server.ts` loads each tab's data with `Promise.allSettled` and per-tab
error capture (matching the existing reports/audit pattern). Role guard
(`user?.role !== 'admin'` → 403) already present.

### 7.2 Users tab — `AdminUsersTable.svelte`

- Search box (debounced, writes `q` to URL) + status & role filter chips
  (URL state, per web patterns "URL as state").
- Table rows: username, email, role, **status badge** (active/suspended/banned),
  joined date. Row actions: **Ban**, **Suspend** (date picker), **Reactivate**,
  **Change role** — opened via `UserStatusDialog` which collects a **reason**
  (required) before calling `setUserStatus`.
- Optimistic row update + rollback + `showToast` on failure (reuse the
  `PostActionBar` pattern). Cursor "load more".
- Self-row actions disabled in the UI (defense-in-depth; backend also guards).

### 7.3 Metrics tab — `AdminMetricsPanel.svelte`

- Calls the existing `getAdminMetrics()` and renders stat cards (total users /
  posts / interactions, posts 24h / 7d) in the glass design system
  (`.glass-surface`, `.text-display-serif`, `.text-mono-meta`).
- Optional: a secondary fetch to analytics-service (`:8091`) for richer series;
  if it errors, the basic cards still render (graceful degradation).

### 7.4 Report-queue polish — `AdminReportsTable.svelte`

- Status filter (pending / resolved / all) via URL param; backend `list_reports`
  already accepts `status` — extend to accept `all`.
- Show post-content snippet + reporter username in each row.
- Bulk resolve: select multiple pending reports → resolve with one action+reason.

### 7.5 API client — `lib/api.ts`

```ts
getAdminUsers(fetcher, { q?, status?, role?, cursor?, limit? }): Promise<CursorPage<AdminUser>>
setUserStatus(fetcher, id, body: SetUserStatusBody): Promise<AdminUser>
```

Types `AdminUser`, `UserStatus`, `SetUserStatusBody` added to `lib/types.ts`.

## 8. Auth, RBAC & security

- All new endpoints reuse the existing admin guard on `/admin/*`.
- Mutations are audit-logged in-transaction (coding rule #5); no admin action is
  silent.
- Self-ban and last-admin-demotion guards prevent lockout.
- Ban/suspend revokes refresh sessions; residual access token window ≤ 15 min
  (access TTL). Documented as accepted; stricter per-request enforcement is a
  noted future option, not in scope.
- Error envelope is the standard `{ error: { code, message } }`.

## 9. Observability & NFRs

- New handlers inherit the service's `http_requests_total` /
  `http_request_duration_seconds` metrics automatically.
- `GET /admin/users` P95 < 150 ms on seeded data (indexed lookups, cursor
  pagination, `limit ≤ 50`).
- `PUT /admin/users/{id}/status` P95 < 200 ms (single tx + Redis revoke).

## 10. Testing & Definition of Done

**Rust (moderation-service smoke + unit):**
- `list_users` returns rows; `q`, `status`, `role` filters narrow correctly;
  cursor paginates.
- `ban` → user row `is_active=false`, audit row written, **login now 403
  `ACCOUNT_BANNED`**.
- `suspend` with future `suspended_until` → login 403 `ACCOUNT_SUSPENDED`;
  after expiry (or with a past timestamp helper) login succeeds again.
- `set_role` changes role + audit row.
- Guards: self-ban rejected; last-admin demotion rejected.

**Rust (auth-service):** banned user login → 403; suspended user → 403;
reactivated user → 200.

**Frontend:** `svelte-check` clean; vitest for the status-derive/badge helper
(active/suspended/banned from `is_active`+`suspended_until`); `AdminUsersTable`
renders rows and disables self-row actions.

**Definition of Done:** all of the above pass; an admin can list/search users,
ban/suspend/reactivate/change-role from the UI with a required reason; a banned
or suspended user is actually blocked at login; every action appears in the
Audit tab; Metrics tab renders; report-queue filter + preview + bulk resolve work.

## 11. Migration & rollout notes

- One new migration (`14`), additive and nullable — safe on existing data.
- The refresh-session reverse index (`session:refresh:user:{id}`) only populates
  going forward; pre-existing sessions for a banned user won't be in the set, so
  on ban also rely on the login/refresh check (they can't refresh into a new
  token because refresh itself now rejects banned/suspended accounts).

## 12. Out of scope / follow-ups

Recommendation-algorithm findings from the same review session (separate plan if
desired):
1. Dead `w4` diversity term in `score_post` (always 0) vs documented formula.
2. `diversity_weight` request param documented but not implemented.
3. Trending & similarity not used as recommender candidate sources;
   `candidates_for_ids` is dead code.
4. Half-life is 36h vs spec's ~6h.
5. Preference vector has no recency decay or cap.

Other: stricter per-request ban enforcement (middleware); appeals workflow;
analytics-service-backed charts in the Metrics tab.
