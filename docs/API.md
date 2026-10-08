# Oecophylla — API Reference

Generated from `backend/services/*/src/{main.rs,handlers.rs,types.rs}`,
`recommendation_api/app/{main.py,schemas.py}` and `services/analytics-service/app/main.py`.
Routing/gateway mapping lives in `envoy/envoy.yaml`; see `docs/SPEC.md §3` for the condensed
path→service table.

- **Base path (public, via Envoy gateway):** `/api/v1/*` and `/admin/*`
- **Auth:** cookie-based JWT — `oec_access` (HttpOnly, 15 min) + `oec_refresh` (HttpOnly, 7 days,
  scoped to `/api/v1/auth`). Endpoints marked 🔒 require a valid `oec_access` cookie;
  🔒admin requires an authenticated user with `role = admin`.
- **Error envelope** (all services, all non-2xx):
  ```json
  { "error": { "code": "...", "message": "..." } }
  ```
- Every HTTP service also exposes `GET /health` and `GET /metrics` (Prometheus) — omitted below
  since they're identical across services.

## Table of contents

1. [auth-service :8001](#1-auth-service-8001)
2. [user-service :8002](#2-user-service-8002)
3. [content-service :8003](#3-content-service-8003)
4. [interaction-service :8004](#4-interaction-service-8004)
5. [feed-service :8005](#5-feed-service-8005)
6. [moderation-service :8006](#6-moderation-service-8006)
7. [notification-service :8007](#7-notification-service-8007)
8. [recommendation-api :8090 (internal)](#8-recommendation-api-8090-internal)
9. [analytics-service :8091 (internal)](#9-analytics-service-8091-internal)

---

## 1. auth-service :8001

Source: `backend/services/auth-service/src/{main.rs,handlers.rs}`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/register` | — | Create an account, sets `oec_access`/`oec_refresh` cookies |
| POST | `/api/v1/auth/login` | — | Log in with email or username, sets cookies |
| POST | `/api/v1/auth/refresh` | refresh cookie | Rotate access token from `oec_refresh` |
| DELETE | `/api/v1/auth/logout` | 🔒 | Clear auth cookies |
| GET | `/api/v1/auth/me` | 🔒 | Return the current user |
| PUT | `/api/v1/auth/password` | 🔒 | Change password (requires current password) |
| DELETE | `/api/v1/auth/account` | 🔒 | Delete own account (requires password confirmation) |

### POST `/api/v1/auth/register`

Request `RegisterReq`:
```json
{
  "username": "string, 3-30 chars, ^[a-z0-9_]+$",
  "email": "string, valid email",
  "password": "string, 8-128 chars",
  "display_name": "string | null"
}
```
Response: `AuthBody` → `{ "user": UserDto }` (see below), plus `Set-Cookie` headers.

### POST `/api/v1/auth/login`

Request `LoginReq`: `{ "email_or_username": "string", "password": "string" }`
Response: `AuthBody`. Inactive accounts are rejected with `401` for both email and username login.

### POST `/api/v1/auth/refresh`

No body — reads `oec_refresh` cookie. Response: `AuthBody` with rotated cookies. Inactive accounts receive `401`; `/auth/me` also rejects them.

### DELETE `/api/v1/auth/logout`

No body. Clears both cookies. `204 No Content`.

### GET `/api/v1/auth/me`

Response: `AuthBody`.

### PUT `/api/v1/auth/password`

Request `ChangePasswordReq`: `{ "current_password": "string", "new_password": "string, >=8 chars" }`
Response: `204 No Content`.

### DELETE `/api/v1/auth/account`

Request `DeleteAccountReq`: `{ "password": "string" }`
Response: `204 No Content`, clears cookies and deactivates the account. This endpoint does not physically erase the user or cascade-delete raw telemetry.

**`UserDto`** (embedded in `AuthBody` and reused elsewhere):
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "role": "user | admin",
  "display_name": "string | null",
  "avatar_url": "string | null",
  "topic_prefs": ["string"]
}
```

---

## 2. user-service :8002

Source: `backend/services/user-service/src/{main.rs,handlers.rs}`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/users` | — | Search users, `?q=&type=&page=&limit=` |
| GET | `/api/v1/users/suggestions` | 🔒 | Follow suggestions, `?limit=` |
| GET | `/api/v1/users/{id}` | — | Get a profile |
| PUT | `/api/v1/users/{id}` | 🔒 (self) | Update own profile |
| GET | `/api/v1/users/{id}/avatar` | — | Redirect/stream avatar image |
| PUT | `/api/v1/users/{id}/avatar` | 🔒 (self) | Upload avatar, multipart, max 5 MiB |
| GET | `/api/v1/users/{id}/cover` | — | Stream profile cover image |
| PUT | `/api/v1/users/{id}/cover` | 🔒 (self) | Upload profile cover, multipart, max 5 MiB |
| POST | `/api/v1/users/{id}/follow` | 🔒 | Follow a user |
| DELETE | `/api/v1/users/{id}/follow` | 🔒 | Unfollow a user |
| GET | `/api/v1/users/{id}/followers` | — | List followers, `?limit=` |
| GET | `/api/v1/users/{id}/following` | — | List who `{id}` follows, `?limit=` |
| GET | `/api/v1/users/{id}/preferences` | 🔒 (self) | Read stored topic preference vector |

### GET `/api/v1/users`

Query `SearchQ`: `q?: string`, `type?: string`, `page?: i64`, `limit?: i64`
Response `UserSearchResponse`: `{ "items": [ProfileRow], "total": number | null, "page": number }`

### PUT `/api/v1/users/{id}`

Request `UpdateProfileReq` (all optional — send only fields to change):
```json
{
  "display_name": "string | null",
  "bio": "string | null",
  "avatar_url": "string | null",
  "topic_prefs": "[\"string\"] | \"null\""
}
```

Profile updates accept validated HTTPS avatar URLs or the same user’s currently stored upload URL. Arbitrary relative URLs are rejected.

### PUT `/api/v1/users/{id}/avatar`

`multipart/form-data` image upload. Response `AvatarUploadResponse`: `{ "avatar_url": "string" }`.

### PUT `/api/v1/users/{id}/cover`

Send one `cover` file as `multipart/form-data`. JPEG, PNG and WebP are accepted up to 5 MiB; MIME type, extension and file signature must agree. Response: `{ "cover_url": "/api/v1/users/{id}/cover?v=..." }`. Profile responses include `cover_url`.

### GET `/api/v1/users/{id}/followers` / `/following`

Query `PageQ`: `limit?: i64`. Response: array of profile summaries.

### GET `/api/v1/users/{id}/preferences`

Response: the user's stored preference vector (topics → weight), used by recommendation-api.

---

## 3. content-service :8003

Source: `backend/services/content-service/src/{main.rs,handlers.rs,update.rs}`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/posts` | 🔒 | Create a post |
| GET | `/api/v1/posts` | — | List posts, cursor-paginated |
| GET | `/api/v1/posts/{id}` | Public if published; owner/admin otherwise | Unpublished posts return `404` to other viewers |
| PUT | `/api/v1/posts/{id}` | 🔒 (author) | Replace editable fields |
| PATCH | `/api/v1/posts/{id}` | 🔒 (author) | Partially update editable fields |
| DELETE | `/api/v1/posts/{id}` | 🔒 (author) | Soft-delete a post |
| POST | `/api/v1/posts/{id}/view` | — | Record a view (fire-and-forget) |
| POST | `/api/v1/posts/{id}/images` | 🔒 (author/admin) | Upload one post image, max 5 MiB |
| GET | `/api/v1/posts/{id}/images/{image_id}` | Public if published; author/admin otherwise | Stream an attached image |
| DELETE | `/api/v1/posts/{id}/images/{image_id}` | 🔒 (author/admin) | Remove an uploaded image |
| GET | `/api/v1/search` | — | Full-text post search |

### POST `/api/v1/posts`

Request `CreatePostReq`:
```json
{
  "content": "string, required",
  "media_urls": ["string"],
  "tags": ["string"],
  "topics": ["string"]
}
```
Response: the created `PostRow` (`201`). Emits a `content.created` Kafka event.

To attach a device image, create the post, then POST a `multipart/form-data` field named `image` to `/api/v1/posts/{id}/images`. The upload returns `{ "image_url": "..." }` and appends the URL to `media_urls`. A post can contain up to six images. JPEG, PNG and WebP files are accepted up to 5 MiB each. Uploaded image URLs in subsequent post updates must already belong to that post.

### GET `/api/v1/posts`

Query `ListQ`: `author_id?: uuid`, `tag?: string`, `topic?: string`, `cursor?: string`, `limit?: i64` (default 20, max 100).
Response `ListResponse`: `{ "items": [PostRow], "next_cursor": "string | null" }`.

### PUT / PATCH `/api/v1/posts/{id}`

Request `UpdatePostInput` — at least one field required:
```json
{
  "content": "string, 1..4000 chars",
  "media_urls": ["string"],
  "tags": ["string"],
  "topics": ["string"]
}
```

### DELETE `/api/v1/posts/{id}`

No body. `204 No Content`. Author-only, soft delete.

### GET `/api/v1/search`

Query `SearchQ`: `q?: string` (min 2 chars, else empty result), `type?: string`, `cursor?: string`, `limit?: i64`.
Response `SearchResponse`: `{ "items": [SearchPostRow], "next_cursor": "string | null" }`.

---

## 4. interaction-service :8004

Source: `backend/services/interaction-service/src/{main.rs,handlers.rs}`

Routes are grouped under separate rate-limit tiers (requests/min shown in parentheses).

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| GET | `/api/v1/posts/saved` | 🔒 | 60/min | List the caller's saved posts |
| POST/DELETE | `/api/v1/posts/{id}/like` | 🔒 | 120/min | Like / unlike a post |
| POST/DELETE | `/api/v1/posts/{id}/save` | 🔒 | 120/min | Save / unsave a post |
| POST/DELETE | `/api/v1/posts/{id}/share` | 🔒 | 120/min | Share / unshare a post |
| POST/DELETE | `/api/v1/posts/{id}/hide` | 🔒 | 120/min | Hide / unhide a post from own feed |
| POST | `/api/v1/posts/{id}/report` | 🔒 | 10/min | Report a post to moderation |
| GET | `/api/v1/posts/{id}/comments` | — | 20/min | List top-level comments |
| POST | `/api/v1/posts/{id}/comments` | 🔒 | 20/min | Create a comment or reply |
| GET | `/api/v1/posts/{id}/comments/stream` | — | 20/min | SSE stream of new comments |
| GET | `/api/v1/comments/{id}/replies` | — | 20/min | List replies to a comment |
| DELETE | `/api/v1/comments/{id}` | 🔒 (author) | 20/min | Delete a comment |
| GET | `/api/v1/posts/{id}/me` | 🔒 | 200/min | Caller's interaction state for one post |
| POST | `/api/v1/interactions/me/batch` | 🔒 | 200/min | Caller's interaction state for many posts |
| POST | `/api/v1/interactions/events/batch` | 🔒 | 600/min | Ingest raw behavior-tracking events |

### POST/DELETE `/api/v1/posts/{id}/{like,save,share,hide}`

No body. `204 No Content`. Idempotent.

### POST `/api/v1/posts/{id}/report`

Request `ReportReq`: `{ "reason": "string", "detail": "string | null" }`

### POST `/api/v1/posts/{id}/comments`

Request `CommentReq`: `{ "content": "string", "parent_comment_id": "uuid | null" }`

### GET `/api/v1/posts/{id}/comments` / `/api/v1/comments/{id}/replies`

Query `CommentsPage`: `limit?: i64`. Response: `CommentsPage` of comment DTOs.

### GET `/api/v1/posts/saved`

Query `SavedQuery`: `cursor?: string`, `limit?: i64`.
Response `SavedResponse`: `{ "items": [SavedPostRow], "next_cursor": "string | null" }`.

### GET `/api/v1/posts/{id}/me`

Response: `MyInteractions` — booleans/flags for liked/saved/shared/hidden/reported by the caller.

### POST `/api/v1/interactions/me/batch`

Request `BatchMeRequest`: `{ "post_ids": ["uuid"] }`
Response `BatchMeResponse`: `{ "items": { "<post_id>": MyInteractionState } }`.

### POST `/api/v1/interactions/events/batch`

Request `BehaviorBatchRequest`: `{ "events": [RawBehaviorEvent] }` where each raw event is:
```json
{
  "client_event_id": "uuid",
  "post_id": "uuid",
  "impression_id": "uuid | null",
  "session_id": "uuid | null",
  "event_type": "string",
  "event_version": "string | null",
  "dwell_ms": "number | null",
  "metadata": {"...": "max 8KiB serialized"},
  "occurred_at": "RFC3339 datetime"
}
```
Response `BehaviorBatchResponse`:
```json
{
  "accepted": 0,
  "duplicate": 0,
  "rejected": 0,
  "errors": [{ "index": 0, "code": "string", "message": "string" }]
}
```
Feeds the MIND-aligned label pipeline (`recommendation_label/`) — see `docs/SPEC.md §6`.

---

## 5. feed-service :8005

Source: `backend/services/feed-service/src/{main.rs,handlers.rs,types.rs}`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/feed` | 🔒 | Personalized feed (cached, ranked) |
| GET | `/api/v1/feed/trending/stream` | — | SSE stream of trending posts |
| GET | `/api/v1/feed/trending/topics` | — | Currently trending topics |

### GET `/api/v1/feed`

Query `FeedQuery`: `cursor?: string`, `limit?: usize`, `mode?: "following" | "trending" | null` (default: ranked/for-you).
Response `FeedResponse`:
```json
{
  "request_id": "uuid",
  "model_version": "string",
  "items": [
    {
      "...PostRow fields (flattened)": "...",
      "rank": { "score": 0.0, "source": "string", "reason": "string" },
      "impression_id": "uuid | null",
      "position": 0
    }
  ],
  "next_cursor": "string | null",
  "source": "string",
  "generated_at": "datetime"
}
```
Calls recommendation-api internally with a fallback to the trending feed on 5xx or >500 ms
(see `backend/services/feed-service/src/recommendation.rs` and coding rule #6 in `CLAUDE.md`).

### GET `/api/v1/feed/trending/topics`

Response: `TrendingTopic[]`.

---

## 6. moderation-service :8006

Source: `backend/services/moderation-service/src/{main.rs,handlers.rs,types.rs}`

All routes require 🔒admin.

| Method | Path | Description |
|---|---|---|
| GET | `/admin/reports` | List reports, `?status=&cursor=&limit=` |
| GET | `/admin/reports/{id}` | Get one report's detail |
| POST | `/admin/reports/{id}/resolve` | Resolve a report (writes `audit_logs`) |
| GET | `/admin/audit-logs` | List audit log entries, `?actor_id=&action=&cursor=&limit=` |
| GET | `/admin/users/{id}/history` | A user's reports + audit history |
| GET | `/admin/metrics` | Dashboard counters |

### GET `/admin/reports`

Query `ReportListQuery`: `status?: string`, `cursor?: string`, `limit?: usize`.
Response `ReportListResponse`: `{ "items": [ReportListItem], "next_cursor": "string | null" }`.

### GET `/admin/reports/{id}`

Response: `ReportDetail`.

### POST `/admin/reports/{id}/resolve`

Request `ResolveRequest`:
```json
{
  "action": "dismiss | hide_post | warn_author | ban_author",
  "note": "string | null"
}
```
Response: `ResolveResponse`. `409 Conflict` (`report_already_resolved`) if the report isn't `pending`.
Writes to `audit_logs` in the same transaction (coding rule #5).

### GET `/admin/audit-logs`

Query `AuditListQuery`: `actor_id?: uuid`, `action?: string`, `cursor?: string`, `limit?: usize`.
Response `AuditListResponse`: `{ "items": [AuditListItem], "next_cursor": "string | null" }`.

### GET `/admin/users/{id}/history`

Response `UserHistoryResponse`: `{ "user_id": "uuid", "reports": [ReportListItem], "audit_entries": [AuditListItem] }`.

### GET `/admin/metrics`

Response `DashboardMetrics`:
```json
{
  "total_users": 0,
  "total_posts": 0,
  "total_interactions": 0,
  "posts_last_24h": 0,
  "posts_last_7d": 0,
  "active_users_24h": 0,
  "pending_reports": 0
}
```

---

## 7. notification-service :8007

Source: `backend/services/notification-service/src/{main.rs,handlers.rs,types.rs}`

All routes require 🔒.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/notifications` | List, `?cursor=&limit=&unread_only=` |
| GET | `/api/v1/notifications/unread-count` | Unread count |
| POST | `/api/v1/notifications/read-all` | Mark all as read |
| POST | `/api/v1/notifications/{id}/read` | Mark one as read |
| GET | `/api/v1/notifications/stream` | SSE stream of new notifications |

### GET `/api/v1/notifications`

Query `ListQuery`: `cursor?: string`, `limit?: i64` (default 20, clamped 1-100), `unread_only?: bool`.
Response `NotificationListResponse`: `{ "items": [NotificationDto], "next_cursor": "string | null" }`.

`NotificationDto`:
```json
{
  "id": "uuid",
  "kind": "liked | followed | commented | ...",
  "actor": { "id": "uuid", "username": "string", "avatar_url": "string | null" } ,
  "post": { "id": "uuid", "snippet": "string" } ,
  "comment_id": "uuid | null",
  "payload": {},
  "read": false,
  "created_at": "datetime"
}
```

### GET `/api/v1/notifications/unread-count`

Response `UnreadCountResponse`: `{ "count": 0 }`.

### POST `/api/v1/notifications/read-all` / `/{id}/read`

No body. Marks read; returns the updated count/notification.

### GET `/api/v1/notifications/stream`

`text/event-stream`. Pushes `NotificationDto` events as they're dispatched (Kafka-fed fan-out,
`fanout.rs`).

---

## 8. recommendation-api :8090 (internal)

Source: `recommendation_api/app/{main.py,schemas.py}`. Not exposed through the Envoy gateway —
called only by `feed-service`. Base path has no `/api/v1` prefix.

| Method | Path | Description |
|---|---|---|
| POST | `/recommend/feed/{user_id}` | Rank candidates for one user |
| POST | `/recommend/features/rebuild` | Rebuild preference vector(s) |
| POST | `/recommend/evaluate` | Offline evaluation metrics for one user |

### POST `/recommend/feed/{user_id}`

Request `RecommendFeedRequest`:
```json
{
  "limit": 50,
  "candidate_pool": 300,
  "exclude_post_ids": ["uuid"]
}
```
Response `RecommendFeedResponse`:
```json
{
  "items": [
    {
      "post_id": "uuid",
      "score": 0.0,
      "source": "string",
      "reason": "string",
      "features": {
        "schema_version": "rank-features-v1",
        "topic_relevance": 0.0,
        "freshness": 0.0,
        "safety_score": 0.0,
        "candidate_source": "string",
        "is_followed_author": true,
        "author_affinity": 0.0,
        "heuristic_score": 0.0,
        "ml_score": 0.0
      }
    }
  ],
  "model_version": "string",
  "generated_at": "datetime"
}
```
Ranker mode controlled by `RANKER_MODE` (`heuristic` in production; ML is shadow-only —
see `docs/AI_ML_RELEASE_STATUS.md`).

### POST `/recommend/features/rebuild`

Request `RebuildRequest`: `{ "user_id": "uuid | null" }` (omit to rebuild all).
Response `RebuildResponse`: `{ "users_processed": 0, "duration_ms": 0 }`.

### POST `/recommend/evaluate`

Request `EvaluateRequest`: `{ "user_id": "uuid", "k": 10 }`.
Response `EvaluateResponse`:
```json
{
  "status": "ok | insufficient_data",
  "precision_at_k": 0.0,
  "recall_at_k": 0.0,
  "ndcg_at_k": 0.0,
  "hit_rate": 0.0,
  "catalog_coverage": 0.0,
  "topic_diversity": 0.0,
  "ctr_observed": 0.0,
  "fallback_rate": 0.0,
  "sample_users": 0,
  "sample_impressions": 0,
  "cutoff_at": "datetime",
  "label_window_hours": 24
}
```

---

## 9. analytics-service :8091 (internal)

Source: `services/analytics-service/app/main.py`. Not exposed through the Envoy gateway.

| Method | Path | Description |
|---|---|---|
| GET | `/admin/dashboard` | Aggregate platform counters + top topics |

### GET `/admin/dashboard`

Response:
```json
{
  "total_users": 0,
  "total_posts": 0,
  "total_interactions": 0,
  "posts_24h": 0,
  "posts_7d": 0,
  "active_users_24h": 0,
  "pending_reports": 0,
  "top_topics": [{ "topic": "string", "cnt": 0 }]
}
```
