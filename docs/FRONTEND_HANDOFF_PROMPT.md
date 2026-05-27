# Frontend Handoff Prompt — Oecophylla

Paste everything below into a fresh Claude Code (or other coding agent) session running
in `/Users/nhathaminh/oecophylla`. This is the **frontend-only** work stream. A separate
session is working the backend in parallel — see "Coordination" at the bottom.

---

````markdown
# Oecophylla Frontend — Apple Glass finish + Phase 3 UI

You are the frontend owner for Oecophylla (SvelteKit + Svelte 5 + Tailwind, adapter-node SSR).
Work only inside `frontend/`. The backend is owned by a parallel session — do NOT edit
`backend/`, `recommendation_api/`, `workers/`, `compose.yaml`, or `envoy/envoy.yaml`.

## Read first (auto-loaded context)
- `CLAUDE.md` (root) — "Current State" section: phases shipped, locked decisions.
- Memory files at `/Users/nhathaminh/.claude/projects/-Users-nhathaminh-oecophylla/memory/`
  auto-load. Critical ones: **Tailwind-first** (inline utilities; extract a class only when
  a pattern repeats 3+ times — `.glass-surface`, `.glass-chip`, `.glass-pill`,
  `.glass-button-primary`, `.text-display-serif`, `.text-mono-meta`).
- Plans: `docs/superpowers/plans/2026-05-27-frontend-apple-glass-route-adaptation.md`
  and Tasks 16–18 of `docs/superpowers/plans/2026-05-26-phase-3-moderation-notifications-nlp-plan.md`.
- Spec for the API contract: `docs/superpowers/specs/2026-05-26-phase-3-moderation-notifications-nlp-design.md`.

## Current frontend state
- `pnpm exec svelte-check` is clean (0 errors, ~363 files). Keep it that way.
- `frontend/src/lib/apple-glass/` holds the design-system source (components + CSS modules:
  tokens/atoms/glass/feed/pages/shell/admin/responsive). Treat these as the visual reference.
- `frontend/src/lib/components/` + `frontend/src/routes/` are the REAL working routes. They were
  just adapted toward Apple Glass (commit `62e9dbd`, marked WIP) but **not browser-verified**.
- Auth flow: HttpOnly cookies (`oec_access`, `oec_refresh`). The browser talks ONLY to SvelteKit
  (`localhost:3000`); `hooks.server.ts` proxies `/api/v1/*` to Envoy and forwards cookies. Use
  `apiFetch(fetch, path, init)` from `$lib/api.ts` for all calls. Never hit Envoy directly from the browser.

## Work stream A — Verify & finish the Apple Glass adaptation (do this FIRST)
The 4-task plan `2026-05-27-frontend-apple-glass-route-adaptation.md` is committed as WIP but
unverified. Your job:
1. `make up` (or `docker compose up -d`) to bring the stack up; open `http://localhost:3000`.
   Seed data: `make seed` (50 users / 100 posts / 200 follows; login `seed_000@oec.local` / `Password!123`).
2. Walk every real route and confirm no regression vs. the working Phase 0+1/2A/2B behavior:
   `/`, `/login`, `/register`, `/logout`, `/profile/[id]`, `/post/new`, `/post/[id]`, `/admin`, `/m`.
   Auth submit, feed infinite scroll + view tracker, like/save optimistic, comments + replies,
   report dialog must all still work.
3. Apply the Apple Glass visual system consistently using the existing `apple-glass/` CSS + components.
   Tailwind-first; do not create a parallel CSS taxonomy. Don't route real pages through the mock
   `AppleGlassApp.svelte` state machine — keep SvelteKit load/action structure.
4. Screenshot key breakpoints (320/768/1024/1440) and both states (anon + authed). Verify reduced-motion
   and keyboard nav on the auth form and the post action bar.
5. Keep `pnpm exec svelte-check`, `pnpm vitest run`, and `pnpm build` green.

## Work stream B — Phase 3 UI (notifications + admin), do AFTER A is verified
These were deferred during backend Phase 3. Backend endpoints may still be WIP — build against the
contract below and **degrade gracefully** (if an endpoint 404s/500s, render an empty/placeholder state,
do not crash the page). The backend session will make them live.

### B1 — Notifications API client + store + SSE  (plan Task 16)
- `frontend/src/lib/api/notifications.ts` — typed clients for: list, mark-read, read-all, unread-count.
- `frontend/src/lib/stores/notifications.ts` — writable `{ items, unread, connected }`.
  - `init()` → `GET /notifications?limit=20` + `GET /notifications/unread-count`.
  - `subscribeSSE()` → `new EventSource('/api/v1/notifications/stream', { withCredentials: true })`.
    Handle `event: notification` (prepend row + bump unread) and `event: heartbeat` (no-op).
    Reconnect with exponential back-off 1s→2s→5s→10s (cap) on `error`.

### B2 — NotificationBell + item  (plan Task 17)
- `frontend/src/lib/components/NotificationBell.svelte` — bell SVG + numeric unread badge; click toggles dropdown.
- `frontend/src/lib/components/NotificationItem.svelte` — actor avatar + verb phrase + relative time;
  click marks read + navigates to the post/profile.
- Mount the bell in the topbar/header of `/`. If the layout currently has no Topbar, mount the bell
  at the top of `/` directly. Reuse `.glass-surface`; no new global CSS.

### B3 — `/admin` real reports + audit  (plan Task 18)
- `frontend/src/routes/admin/+page.server.ts` — SSR loader; require `data.user?.role === 'admin'`,
  else `throw error(403)`.
- Replace the mock in `frontend/src/routes/admin/+page.svelte` with a two-tab layout (Reports / Audit):
  - `AdminReportsTable`: paginated `pending` reports (post snippet, reporter, time, reason). Each row has
    4 action buttons + optional note textarea → `POST /admin/reports/:id/resolve` then re-fetch.
    Show a confirm modal only for `ban_author`.
  - `AdminAuditTable`: cursor-paginated audit log; filter by actor + action via query params.

## Backend API contract (build against these exact shapes)

**notification-service** (proxied via Envoy under `/api/v1/notifications`):
```
GET  /api/v1/notifications?cursor=&limit=20&unread_only=false   → { items: Notification[], next_cursor: string|null }
POST /api/v1/notifications/:id/read                              → 204
POST /api/v1/notifications/read-all                             → 204
GET  /api/v1/notifications/unread-count                         → { count: number }
GET  /api/v1/notifications/stream   (SSE; events: `notification` with JSON data, `heartbeat`)
```
Notification row fields: `id, user_id, type, actor_id, post_id?, comment_id?, is_read, created_at`
plus hydrated `actor_username, actor_display_name, snippet?`. Types include `liked`, `commented`,
`comment_replied`, `followed`, `post_hidden`, `author_warned`, `author_banned`, `report_dismissed`.

**moderation-service** (admin, proxied under `/admin`; all require `role=admin`):
```
GET  /admin/reports?status=pending&cursor=&limit=20  → { items: Report[], next_cursor }
GET  /admin/reports/:id                              → Report (with post snippet + reporter)
POST /admin/reports/:id/resolve                      → body { action, note? }; 200
     action ∈ "dismiss" | "hide_post" | "warn_author" | "ban_author"
GET  /admin/audit-logs?actor_id=&action=&cursor=&limit=20  → { items: AuditLog[], next_cursor }
GET  /admin/users/:id/history                        → { reports: [], audit: [] }
```
Resolve semantics: dismiss→resolved_ok; hide_post→resolved_hidden + post hidden; warn_author→resolved_warned;
ban_author→resolved_warned + `users.is_active=false`. Each resolve writes an `audit_logs` row.

## Constraints (non-negotiable)
- Tailwind-first; reuse the 6 glass recipes; no parallel CSS system; no inline `alert()` for new work —
  use the existing `Toast.svelte` (`apple-glass/components/Toast.svelte`) or a small toast store.
- All API calls go through `apiFetch(fetch, ...)` (SSR-proxied, cookie-forwarded). Never embed JWT in JS.
- Svelte 5 syntax where the file already uses runes; otherwise match the file's existing style.
- Keep `pnpm exec svelte-check` at 0 errors, `pnpm vitest run` green, `pnpm build` succeeds before each commit.
- Commit in tidy groups with conventional-commit messages. No `git add -A` — stage explicit paths.
  Do NOT add attribution footers (disabled globally for this repo).

## Definition of done
- Apple Glass adaptation verified in browser at 4 breakpoints, both auth states, no route regression.
- NotificationBell shows live unread count via SSE; clicking an item marks read + navigates.
- `/admin` shows real pending reports + audit log for admin users, 403 for non-admins; resolve actions work
  (or degrade cleanly if the backend endpoint is not live yet).
- svelte-check / vitest / build all green; screenshots attached in your final report.

## Coordination with the backend session
- The backend session is finishing `moderation-service` + `notification-service` (currently WIP) and the
  `nlp-worker`. Their endpoints may 404 until they land. Build to the contract above and degrade gracefully.
- If you need a contract change (field rename, extra field), write it as a note in your final report rather
  than editing backend code — the backend owner will reconcile.
````

---

**End of handoff prompt.**
