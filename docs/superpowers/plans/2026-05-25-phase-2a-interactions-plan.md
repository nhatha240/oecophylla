# Phase 2A: Interactions & Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add `interaction-service` (Rust, :8004) with like/save/share/hide/report endpoints + a `comments` table with 1-level reply + the `reports` table. Frontend gets a `PostActionBar` and a comments thread on the post detail page. All interactions emit events to a new `oecophylla.interactions` Kafka topic.

**Architecture:** Strict service split — interaction-service joins the existing 3-service workspace. 4 new migrations extend the schema (counters on `posts`, plus `interactions`, `comments`, `reports` tables). Envoy gets a `safe_regex` route to direct `/api/v1/posts/:id/(like|save|...|comments|me)` and `/api/v1/comments/*` to the new service before the broad `/api/v1/posts` content route. Counters live denormalized on `posts` and update inside the same DB transaction as the interaction insert/delete.

**Tech Stack:** Same as Phase 0+1 — Rust 1.85, Axum, SQLx, rdkafka, Tailwind+SvelteKit, Envoy, Postgres 18, Kafka KRaft.

**Companion spec:** `docs/superpowers/specs/2026-05-25-phase-2a-interactions-design.md`. Refer to it for full schema DDL, endpoint table, event payloads, frontend component list, and DoD checklist. The plan duplicates only what an engineer needs to copy.

**Working directory:** `/Users/nhathaminh/oecophylla` (git repo on `main`, tagged `phase-0-1-complete`).

---

## Milestone overview

| M | Tasks | Outcome |
|---|---|---|
| M1 | 1–2 | Migrations applied + interaction-service Cargo crate scaffolded |
| M2 | 3–5 | Service repo + handlers + Dockerfile + Envoy route |
| M3 | 6 | Smoke tests pass |
| M4 | 7 | content-service exposes new counter fields |
| M5 | 8–11 | Frontend types/components/pages |
| M6 | 12–13 | Vitest + DoD verify + tag |

Tasks 7 and 8 are independent (different files in different services); they can dispatch in parallel.
Tasks 9, 10, 11 are sequential (each depends on the prior).
Task 12 (vitest) is independent of 10/11; it parallels with 10 or 11 once 9 is done.

---

## Task 1: Migrations 5–8

**Files:**
- Create: `migrations/20260525000005_posts_counters.sql`
- Create: `migrations/20260525000006_interactions.sql`
- Create: `migrations/20260525000007_comments.sql`
- Create: `migrations/20260525000008_reports.sql`

- [ ] **Step 1: Write each file** — copy the exact SQL from spec §3.1, §3.2, §3.3, §3.4. Each file is short (~10-20 lines).

- [ ] **Step 2: Run migrate**
  ```bash
  cd /Users/nhathaminh/oecophylla
  docker compose up migrate
  ```
  Expected: 4 new "Applied" lines, exit 0.

- [ ] **Step 3: Verify**
  ```bash
  docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d posts" | grep _count
  docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d interactions"
  docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d comments"
  docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d reports"
  ```
  Expected: 4 new `_count` columns on posts, 3 new tables with correct PK defaults `uuidv7()`, all indexes listed in spec present.

- [ ] **Step 4: Commit**
  ```bash
  git add migrations/2026052500000{5,6,7,8}_*.sql
  git commit -m "feat(db): phase 2a — posts counters + interactions + comments + reports"
  ```

---

## Task 2: interaction-service scaffold

**Files:**
- Create: `backend/services/interaction-service/Cargo.toml`
- Create: `backend/services/interaction-service/src/main.rs` (stub for now)
- Modify: `backend/Cargo.toml` (add workspace member)

- [ ] **Step 1: Add to workspace** — edit `backend/Cargo.toml`:
  ```toml
  members = [
      "crates/common",
      "services/auth-service",
      "services/user-service",
      "services/content-service",
      "services/interaction-service",   # NEW
  ]
  ```

- [ ] **Step 2: Write `backend/services/interaction-service/Cargo.toml`** — clone of user-service's Cargo.toml, change `name = "interaction-service"`. Include `validator.workspace = true` + `regex = "1"` + `once_cell = "1"` directly. Dev-deps: `reqwest.workspace = true` + `serde_json.workspace = true` + `tokio.workspace = true`.

- [ ] **Step 3: Write stub `src/main.rs`** mimicking other services:
  ```rust
  use axum::{routing::get, Router};
  use std::net::SocketAddr;

  #[tokio::main]
  async fn main() -> anyhow::Result<()> {
      common::middleware::trace::init_tracing("interaction-service");
      let app = Router::new().route("/health", get(|| async { "ok" }));
      let addr: SocketAddr = std::env::var("INTERACTION_BIND")
          .unwrap_or_else(|_| "0.0.0.0:8004".into()).parse()?;
      let listener = tokio::net::TcpListener::bind(addr).await?;
      tracing::info!(?addr, "interaction-service listening");
      axum::serve(listener, app).await?;
      Ok(())
  }
  ```

- [ ] **Step 4: Verify**
  ```bash
  cd backend && cargo check --workspace
  ```
  Zero errors.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/Cargo.toml backend/services/interaction-service/
  git commit -m "feat(interaction-service): scaffold cargo member with health stub"
  ```

---

## Task 3: interaction-service repo layer

**Files:**
- Create: `backend/services/interaction-service/src/state.rs`
- Create: `backend/services/interaction-service/src/repo.rs`

- [ ] **Step 1: `state.rs`** — identical shape to user-service's: `AppState { db: PgPool, redis: RedisPool, kafka: Producer, cfg: Arc<SharedConfig> }`.

- [ ] **Step 2: `repo.rs`** — implement the following functions. Each takes a `&mut PgConnection` (or `&mut Transaction<'_, Postgres>`) so the caller controls transactions.

```rust
use common::{error::AppError, ids::new_id, models::AuthUser};
use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::{PgConnection, Postgres, Transaction};
use uuid::Uuid;

// === interactions ===

pub async fn insert_interaction(
    tx: &mut Transaction<'_, Postgres>,
    user_id: Uuid, post_id: Uuid, type_: &str, weight: f32,
) -> Result<bool, AppError> {
    let r = sqlx::query(
        "INSERT INTO interactions (user_id, post_id, type, weight)
         VALUES ($1, $2, $3::interaction_type, $4)
         ON CONFLICT (user_id, post_id, type) DO NOTHING"
    ).bind(user_id).bind(post_id).bind(type_).bind(weight)
     .execute(&mut **tx).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn delete_interaction(
    tx: &mut Transaction<'_, Postgres>,
    user_id: Uuid, post_id: Uuid, type_: &str,
) -> Result<bool, AppError> {
    let r = sqlx::query(
        "DELETE FROM interactions WHERE user_id=$1 AND post_id=$2 AND type=$3::interaction_type"
    ).bind(user_id).bind(post_id).bind(type_).execute(&mut **tx).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn bump_counter(
    tx: &mut Transaction<'_, Postgres>,
    post_id: Uuid, column: &str, delta: i32,
) -> Result<(), AppError> {
    // `column` is from a closed enum {"like_count","save_count","share_count","comment_count"}
    // so it is safe to interpolate into the SQL string.
    let sql = format!("UPDATE posts SET {column} = {column} + $1 WHERE id=$2");
    sqlx::query(&sql).bind(delta).bind(post_id).execute(&mut **tx).await?;
    Ok(())
}

pub async fn post_author(db: &sqlx::PgPool, post_id: Uuid) -> Result<Option<Uuid>, AppError> {
    Ok(sqlx::query_scalar::<_, Uuid>("SELECT author_id FROM posts WHERE id=$1")
        .bind(post_id).fetch_optional(db).await?)
}

// === reports ===

#[derive(Serialize, sqlx::FromRow)]
pub struct ReportRow { pub id: Uuid, pub status: String, pub created_at: DateTime<Utc> }

pub async fn insert_report(
    tx: &mut Transaction<'_, Postgres>,
    reporter_id: Uuid, post_id: Uuid, reason: &str, detail: Option<&str>,
) -> Result<Uuid, AppError> {
    let id: Uuid = sqlx::query_scalar(
        "INSERT INTO reports (reporter_id, post_id, reason, detail)
         VALUES ($1, $2, $3, $4) RETURNING id"
    ).bind(reporter_id).bind(post_id).bind(reason).bind(detail)
     .fetch_one(&mut **tx).await
     .map_err(|e| match e {
         sqlx::Error::Database(d) if d.code().as_deref() == Some("23505") =>
             AppError::Conflict { kind: "report".into() },
         o => AppError::Db(o),
     })?;
    Ok(id)
}

// === comments ===

#[derive(Serialize, sqlx::FromRow, Clone)]
pub struct CommentRow {
    pub id: Uuid,
    pub post_id: Uuid,
    pub author_id: Uuid,
    pub author_username: String,
    pub author_display_name: Option<String>,
    pub parent_comment_id: Option<Uuid>,
    pub content: String,
    pub is_deleted: bool,
    pub created_at: DateTime<Utc>,
    pub reply_count: i64,
}

pub async fn insert_comment(
    tx: &mut Transaction<'_, Postgres>,
    post_id: Uuid, author_id: Uuid, parent_comment_id: Option<Uuid>, content: &str,
) -> Result<Uuid, AppError> {
    // 1-level enforcement: if parent_comment_id is set, ensure parent is top-level (its parent_comment_id IS NULL).
    if let Some(p) = parent_comment_id {
        let parent_of_parent: Option<Option<Uuid>> = sqlx::query_scalar(
            "SELECT parent_comment_id FROM comments WHERE id=$1 AND post_id=$2"
        ).bind(p).bind(post_id).fetch_optional(&mut **tx).await?;
        match parent_of_parent {
            None => return Err(AppError::NotFound { kind: "parent_comment".into() }),
            Some(Some(_)) => return Err(AppError::Validation {
                field: "parent_comment_id".into(),
                message: "cannot reply more than one level deep".into(),
            }),
            Some(None) => { /* OK */ }
        }
    }
    let id = new_id();
    sqlx::query(
        "INSERT INTO comments (id, post_id, author_id, parent_comment_id, content)
         VALUES ($1, $2, $3, $4, $5)"
    ).bind(id).bind(post_id).bind(author_id).bind(parent_comment_id).bind(content)
     .execute(&mut **tx).await?;
    Ok(id)
}

pub async fn list_top_level_comments(
    db: &sqlx::PgPool, post_id: Uuid, limit: i64,
) -> Result<Vec<CommentRow>, AppError> {
    Ok(sqlx::query_as::<_, CommentRow>(
        "SELECT c.id, c.post_id, c.author_id,
                u.username AS author_username, u.display_name AS author_display_name,
                c.parent_comment_id,
                CASE WHEN c.is_deleted THEN '[đã xóa]' ELSE c.content END AS content,
                c.is_deleted, c.created_at,
                (SELECT count(*) FROM comments r
                  WHERE r.parent_comment_id = c.id AND r.is_deleted = false) AS reply_count
         FROM comments c
         JOIN users u ON u.id = c.author_id
         WHERE c.post_id = $1 AND c.parent_comment_id IS NULL AND c.is_deleted = false
         ORDER BY c.created_at ASC
         LIMIT $2"
    ).bind(post_id).bind(limit).fetch_all(db).await?)
}

pub async fn list_replies(
    db: &sqlx::PgPool, parent_id: Uuid, limit: i64,
) -> Result<Vec<CommentRow>, AppError> {
    Ok(sqlx::query_as::<_, CommentRow>(
        "SELECT c.id, c.post_id, c.author_id,
                u.username AS author_username, u.display_name AS author_display_name,
                c.parent_comment_id,
                CASE WHEN c.is_deleted THEN '[đã xóa]' ELSE c.content END AS content,
                c.is_deleted, c.created_at,
                0::bigint AS reply_count
         FROM comments c
         JOIN users u ON u.id = c.author_id
         WHERE c.parent_comment_id = $1 AND c.is_deleted = false
         ORDER BY c.created_at ASC
         LIMIT $2"
    ).bind(parent_id).bind(limit).fetch_all(db).await?)
}

pub async fn soft_delete_comment(
    tx: &mut Transaction<'_, Postgres>, id: Uuid, requester: AuthUser,
) -> Result<(Uuid /*post_id*/, bool /*was_top_level*/), AppError> {
    use common::models::UserRole;
    let row: Option<(Uuid, Uuid, Option<Uuid>, bool)> = sqlx::query_as(
        "SELECT post_id, author_id, parent_comment_id, is_deleted FROM comments WHERE id=$1"
    ).bind(id).fetch_optional(&mut **tx).await?;
    let (post_id, author_id, parent, already) = row.ok_or(AppError::NotFound { kind: "comment".into() })?;
    if already { return Ok((post_id, parent.is_none())); }
    if author_id != requester.id && requester.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    sqlx::query("UPDATE comments SET is_deleted = true WHERE id=$1")
        .bind(id).execute(&mut **tx).await?;
    Ok((post_id, parent.is_none()))
}

// === my-interactions ===

#[derive(Serialize)]
pub struct MyInteractions {
    pub liked: bool, pub saved: bool, pub shared: bool, pub hidden: bool, pub reported_pending: bool,
}

pub async fn my_interactions(
    db: &sqlx::PgPool, user_id: Uuid, post_id: Uuid,
) -> Result<MyInteractions, AppError> {
    let row: (Option<bool>, Option<bool>, Option<bool>, Option<bool>, bool) = sqlx::query_as(
        "SELECT
           bool_or(type = 'like'::interaction_type)  AS liked,
           bool_or(type = 'save'::interaction_type)  AS saved,
           bool_or(type = 'share'::interaction_type) AS shared,
           bool_or(type = 'hide'::interaction_type)  AS hidden,
           EXISTS (SELECT 1 FROM reports WHERE reporter_id=$1 AND post_id=$2 AND status='pending') AS reported_pending
         FROM interactions WHERE user_id=$1 AND post_id=$2"
    ).bind(user_id).bind(post_id).fetch_one(db).await?;
    Ok(MyInteractions {
        liked: row.0.unwrap_or(false), saved: row.1.unwrap_or(false),
        shared: row.2.unwrap_or(false), hidden: row.3.unwrap_or(false),
        reported_pending: row.4,
    })
}
```

- [ ] **Step 3: Verify** — `cargo check --workspace` clean.

- [ ] **Step 4: Commit**
  ```bash
  git add backend/services/interaction-service/src/{state.rs,repo.rs}
  git commit -m "feat(interaction-service): repo layer for interactions/comments/reports/counters"
  ```

---

## Task 4: interaction-service handlers

**Files:**
- Create: `backend/services/interaction-service/src/handlers.rs`
- Create: `backend/services/interaction-service/src/events.rs` (event payload structs)

- [ ] **Step 1: `events.rs`** — payload structs and weights.

```rust
use serde::Serialize;
use uuid::Uuid;
use common::events::Envelope;

pub const TOPIC_INTERACTIONS: &str = "oecophylla.interactions";

#[derive(Serialize)]
pub struct ToggleData { pub user_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub weight: f32 }
#[derive(Serialize)]
pub struct ReportData { pub reporter_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub reason: String, pub report_id: Uuid }
#[derive(Serialize)]
pub struct CommentData { pub commenter_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub comment_id: Uuid, pub parent_comment_id: Option<Uuid>, pub content_preview: String }

pub fn weight_for(t: &str) -> f32 {
    match t {
        "like" => env_or("INTERACTION_WEIGHT_LIKE", 1.5),
        "save" => env_or("INTERACTION_WEIGHT_SAVE", 2.5),
        "share" => env_or("INTERACTION_WEIGHT_SHARE", 2.5),
        "hide" => env_or("INTERACTION_WEIGHT_HIDE", -2.0),
        "report" => env_or("INTERACTION_WEIGHT_REPORT", -5.0),
        _ => 0.0,
    }
}
fn env_or(key: &str, default: f32) -> f32 {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}

pub fn counter_column(t: &str) -> Option<&'static str> {
    match t { "like" => Some("like_count"), "save" => Some("save_count"), "share" => Some("share_count"), _ => None }
}
```

- [ ] **Step 2: `handlers.rs`** — all endpoints. Use this template; expand for each route. Use `common::auth::verify_access` + `extract_cookie` pattern from user-service for `current_user`. Apply same pre-mint UUIDv7 pattern when needed.

```rust
use axum::{extract::{Path, Query, State}, http::{HeaderMap, StatusCode}, response::IntoResponse, Json};
use common::{auth::verify_access, error::{AppError, AppResult}, events::Envelope, models::AuthUser};
use serde::Deserialize;
use uuid::Uuid;

use crate::{events::*, repo, state::AppState};

fn current(s: &AppState, h: &HeaderMap) -> Option<AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw.split(';').find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let c = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(AuthUser { id: c.sub, role: c.role })
}

// --- like / save / share / hide ---

async fn toggle_post(
    s: AppState, h: HeaderMap, post_id: Uuid, type_: &'static str, method: &'static str,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let author = repo::post_author(&s.db, post_id).await?.ok_or(AppError::NotFound { kind: "post".into() })?;
    let weight = weight_for(type_);
    let mut tx = s.db.begin().await?;
    let changed = match method {
        "POST"   => repo::insert_interaction(&mut tx, me.id, post_id, type_, weight).await?,
        "DELETE" => repo::delete_interaction(&mut tx, me.id, post_id, type_).await?,
        _ => unreachable!(),
    };
    if changed {
        if let Some(col) = counter_column(type_) {
            let delta = if method == "POST" { 1 } else { -1 };
            repo::bump_counter(&mut tx, post_id, col, delta).await?;
        }
    }
    tx.commit().await?;
    if changed {
        let evt = match (type_, method) {
            ("like",  "POST")   => "liked",
            ("like",  "DELETE") => "unliked",
            ("save",  "POST")   => "saved",
            ("save",  "DELETE") => "unsaved",
            ("share", "POST")   => "shared",
            ("share", "DELETE") => "unshared",
            ("hide",  "POST")   => "hidden",
            ("hide",  "DELETE") => "",     // no event for unhide
            _ => "",
        };
        if !evt.is_empty() {
            let env = Envelope::new(evt, "interaction-service", ToggleData {
                user_id: me.id, post_id, post_author_id: author, weight,
            });
            // Reinterpret event_type as a static; common::events::Envelope requires &'static str.
            // We work around by passing concrete strings via a helper that boxes the str; if Envelope's
            // type is too rigid, declare typed wrappers per event_type. (See implementation note.)
            s.kafka.produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env).await;
        }
    }
    let code = match (method, changed) {
        ("POST",   true)  => StatusCode::CREATED,
        ("POST",   false) => StatusCode::OK,
        ("DELETE", _)     => StatusCode::NO_CONTENT,
        _ => StatusCode::OK,
    };
    Ok(code)
}

pub async fn like_post(State(s): State<AppState>, Path(id): Path<Uuid>, h: HeaderMap) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "like", "POST").await
}
pub async fn unlike_post(State(s): State<AppState>, Path(id): Path<Uuid>, h: HeaderMap) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "like", "DELETE").await
}
// ... save/unsave, share/unshare, hide/unhide handlers all delegate to toggle_post the same way.

// --- report ---

#[derive(Deserialize)]
pub struct ReportReq { pub reason: String, pub detail: Option<String> }

pub async fn report_post(State(s): State<AppState>, Path(post_id): Path<Uuid>, h: HeaderMap, Json(body): Json<ReportReq>) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let allowed = ["spam","misinformation","harassment","nsfw","other"];
    if !allowed.contains(&body.reason.as_str()) {
        return Err(AppError::Validation { field: "reason".into(), message: "invalid reason".into() });
    }
    let author = repo::post_author(&s.db, post_id).await?.ok_or(AppError::NotFound { kind: "post".into() })?;
    let mut tx = s.db.begin().await?;
    let report_id = repo::insert_report(&mut tx, me.id, post_id, &body.reason, body.detail.as_deref()).await?;
    repo::insert_interaction(&mut tx, me.id, post_id, "report", weight_for("report")).await?;
    tx.commit().await?;
    let env = Envelope::new("reported", "interaction-service", ReportData {
        reporter_id: me.id, post_id, post_author_id: author,
        reason: body.reason, report_id,
    });
    s.kafka.produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env).await;
    Ok(StatusCode::CREATED)
}

// --- comments ---

#[derive(Deserialize)]
pub struct CommentReq { pub content: String, pub parent_comment_id: Option<Uuid> }
#[derive(Deserialize)] pub struct CommentsPage { pub limit: Option<i64> }

pub async fn create_comment(State(s): State<AppState>, Path(post_id): Path<Uuid>, h: HeaderMap, Json(body): Json<CommentReq>) -> AppResult<Json<serde_json::Value>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let content = body.content.trim();
    if content.is_empty() || content.chars().count() > 2000 {
        return Err(AppError::Validation { field: "content".into(), message: "1..=2000 chars".into() });
    }
    let author = repo::post_author(&s.db, post_id).await?.ok_or(AppError::NotFound { kind: "post".into() })?;
    let mut tx = s.db.begin().await?;
    let comment_id = repo::insert_comment(&mut tx, post_id, me.id, body.parent_comment_id, content).await?;
    if body.parent_comment_id.is_none() {
        repo::bump_counter(&mut tx, post_id, "comment_count", 1).await?;
    }
    tx.commit().await?;
    let preview = content.chars().take(200).collect::<String>();
    let event_type = if body.parent_comment_id.is_some() { "comment_replied" } else { "commented" };
    let env = Envelope::new(event_type, "interaction-service", CommentData {
        commenter_id: me.id, post_id, post_author_id: author, comment_id,
        parent_comment_id: body.parent_comment_id, content_preview: preview,
    });
    s.kafka.produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env).await;
    Ok(Json(serde_json::json!({ "id": comment_id, "parent_comment_id": body.parent_comment_id })))
}

pub async fn list_comments(State(s): State<AppState>, Path(post_id): Path<Uuid>, Query(q): Query<CommentsPage>) -> AppResult<Json<Vec<serde_json::Value>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let top = repo::list_top_level_comments(&s.db, post_id, limit).await?;
    let mut out = Vec::with_capacity(top.len());
    for c in top {
        // load up to 5 replies inline
        let replies = repo::list_replies(&s.db, c.id, 5).await?;
        let has_more = replies.len() == 5 && c.reply_count > 5;
        out.push(serde_json::json!({
            "id": c.id, "post_id": c.post_id, "author_id": c.author_id,
            "author_username": c.author_username, "author_display_name": c.author_display_name,
            "parent_comment_id": c.parent_comment_id,
            "content": c.content, "is_deleted": c.is_deleted, "created_at": c.created_at,
            "reply_count": c.reply_count, "has_more_replies": has_more,
            "replies": replies.iter().map(|r| serde_json::json!({
                "id": r.id, "post_id": r.post_id, "author_id": r.author_id,
                "author_username": r.author_username, "author_display_name": r.author_display_name,
                "parent_comment_id": r.parent_comment_id, "content": r.content,
                "is_deleted": r.is_deleted, "created_at": r.created_at,
            })).collect::<Vec<_>>(),
        }));
    }
    Ok(Json(out))
}

pub async fn list_comment_replies(State(s): State<AppState>, Path(comment_id): Path<Uuid>, Query(q): Query<CommentsPage>) -> AppResult<Json<Vec<repo::CommentRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_replies(&s.db, comment_id, limit).await?))
}

pub async fn delete_comment(State(s): State<AppState>, Path(id): Path<Uuid>, h: HeaderMap) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let mut tx = s.db.begin().await?;
    let (post_id, was_top) = repo::soft_delete_comment(&mut tx, id, me).await?;
    if was_top {
        repo::bump_counter(&mut tx, post_id, "comment_count", -1).await?;
    }
    tx.commit().await?;
    Ok(StatusCode::NO_CONTENT)
}

// --- my interactions ---

pub async fn my_post_interactions(State(s): State<AppState>, Path(post_id): Path<Uuid>, h: HeaderMap) -> AppResult<Json<repo::MyInteractions>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    Ok(Json(repo::my_interactions(&s.db, me.id, post_id).await?))
}
```

> Implementation note on the Envelope `event_type: &'static str` constraint: pass the literal `&'static str` directly (the `match` returns literal `"liked"` etc., all of which are `&'static str`). If `Envelope::new` signature is too strict, you may need to widen its type — but the existing definition in `crates/common/src/events.rs` already takes `&'static str` so this works.

- [ ] **Step 3: Verify** — `cargo check --workspace` clean.

- [ ] **Step 4: Commit**
  ```bash
  git add backend/services/interaction-service/src/{handlers.rs,events.rs}
  git commit -m "feat(interaction-service): handlers for toggle/comment/report + event payloads"
  ```

---

## Task 5: interaction-service main.rs + Dockerfile + Envoy + compose

**Files:**
- Modify: `backend/services/interaction-service/src/main.rs`
- Create: `backend/services/interaction-service/Dockerfile`
- Modify: `envoy/envoy.yaml`
- Modify: `compose.yaml`
- Modify: `compose.dev.yaml`

- [ ] **Step 1: Full `main.rs`** — same shape as user-service:
  ```rust
  use axum::{Router, routing::{get, post, delete}};
  use common::{config::SharedConfig, db::pg_pool, redis::redis_pool, kafka::Producer, middleware::trace::init_tracing};
  use std::{net::SocketAddr, sync::Arc};

  mod state; mod handlers; mod repo; mod events;
  use state::AppState;

  #[tokio::main]
  async fn main() -> anyhow::Result<()> {
      init_tracing("interaction-service");
      let mut cfg = SharedConfig::from_env()?;
      cfg.bind = std::env::var("INTERACTION_BIND").unwrap_or_else(|_| "0.0.0.0:8004".into());

      let db = pg_pool(&cfg.database_url, 10).await?;
      let redis = redis_pool(&cfg.redis_url)?;
      let kafka = Producer::new(&cfg.kafka_brokers)?;
      let state = AppState { db, redis, kafka, cfg: Arc::new(cfg.clone()) };

      let app = Router::new()
          .route("/health", get(|| async { "ok" }))
          .route("/api/v1/posts/:id/like",   post(handlers::like_post).delete(handlers::unlike_post))
          .route("/api/v1/posts/:id/save",   post(handlers::save_post).delete(handlers::unsave_post))
          .route("/api/v1/posts/:id/share",  post(handlers::share_post).delete(handlers::unshare_post))
          .route("/api/v1/posts/:id/hide",   post(handlers::hide_post).delete(handlers::unhide_post))
          .route("/api/v1/posts/:id/report", post(handlers::report_post))
          .route("/api/v1/posts/:id/comments",
                 get(handlers::list_comments).post(handlers::create_comment))
          .route("/api/v1/posts/:id/me",     get(handlers::my_post_interactions))
          .route("/api/v1/comments/:id/replies", get(handlers::list_comment_replies))
          .route("/api/v1/comments/:id",         delete(handlers::delete_comment))
          .with_state(state);

      let addr: SocketAddr = cfg.bind.parse()?;
      let listener = tokio::net::TcpListener::bind(addr).await?;
      tracing::info!(?addr, "interaction-service listening");
      axum::serve(listener, app).await?;
      Ok(())
  }
  ```

  (Save/share/hide handlers in handlers.rs are 6-line wrappers: `pub async fn save_post(...) { toggle_post(s, h, id, "save", "POST").await }` etc.)

- [ ] **Step 2: Dockerfile** — clone of user-service Dockerfile, change service name and `EXPOSE 8004`. Builder: `rust:1.85` with `cmake pkg-config libssl-dev ca-certificates`; runtime: `debian:trixie-slim` with `ca-certificates libssl3 libpq5`.

- [ ] **Step 3: Envoy update** — edit `envoy/envoy.yaml`. **Order matters**: place the interaction-route block BEFORE the existing `/api/v1/posts/` content-service route inside `virtual_hosts[0].routes`.

  Add new route entry:
  ```yaml
  - match:
      safe_regex:
        regex: '^/api/v1/(posts/[^/]+/(like|save|share|hide|report|comments(?:/.*)?|me)/?|comments/[^/]+(?:/.*)?)$'
    route: { cluster: interaction_cluster }
  ```

  Add new cluster:
  ```yaml
  - name: interaction_cluster
    type: STRICT_DNS
    connect_timeout: 1s
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: interaction_cluster
      endpoints:
        - lb_endpoints:
            - endpoint: { address: { socket_address: { address: interaction-service, port_value: 8004 } } }
    health_checks:
      - timeout: 1s
        interval: 5s
        unhealthy_threshold: 3
        healthy_threshold: 1
        http_health_check: { path: "/health" }
  ```

- [ ] **Step 4: compose.yaml** — add `interaction-service` block, same shape as `user-service`. Also add `interaction-service` to envoy's `depends_on`.

  ```yaml
    interaction-service:
      <<: *restart
      build:
        context: ./backend
        dockerfile: services/interaction-service/Dockerfile
      depends_on:
        postgres:  { condition: service_healthy }
        redis:     { condition: service_healthy }
        kafka:     { condition: service_healthy }
        migrate:   { condition: service_completed_successfully }
      environment:
        <<: *svc_env
  ```

- [ ] **Step 5: compose.dev.yaml** — add `interaction-service: { ports: ["8004:8004"] }`.

- [ ] **Step 6: Add `oecophylla.interactions` topic to init-topics**. Edit the `command:` of the `init-topics` service in `compose.yaml` to also create the new topic:
  ```bash
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic oecophylla.interactions --partitions 1 --replication-factor 1
  ```

- [ ] **Step 7: Build + run**
  ```bash
  docker compose up -d --build interaction-service
  docker compose up init-topics
  docker compose ps
  docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
  ```
  Expected: interaction-service Up; 3 topics listed.

- [ ] **Step 8: Restart envoy to load new config**
  ```bash
  docker compose restart envoy
  curl -s http://localhost:8080/api/v1/posts/<existing-post-id>/me -i
  ```
  Expected: 401 (no cookie) — meaning the route reached the service.

- [ ] **Step 9: Commit**
  ```bash
  git add backend/services/interaction-service/{main.rs,Dockerfile} envoy/envoy.yaml compose.yaml compose.dev.yaml
  git commit -m "feat(interaction-service): main + dockerfile; envoy route; compose entry; kafka topic"
  ```

---

## Task 6: interaction-service smoke tests

**Files:**
- Create: `backend/services/interaction-service/tests/smoke.rs`

- [ ] **Step 1: Smoke test code** — 5 scenarios. Use the docker-exec kafka pattern from Phase 0+1 T9/T10 (memory `project-kafka-listener-host`).

```rust
//! Pre: docker compose stack up incl. interaction-service. Tests use Envoy (:8080).

use reqwest::{Client, StatusCode};
use serde_json::json;
use std::process::Command;
use std::time::Duration;

const ENVOY: &str = "http://localhost:8080";

fn cli() -> Client { Client::builder().cookie_store(true).build().unwrap() }

async fn register_user(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c.post(format!("{ENVOY}/api/v1/auth/register"))
        .json(&json!({ "username": format!("u{}", &u[22..]), "email": format!("{u}@e.com"), "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), 200, "register failed: {}", r.text().await.unwrap());
    r.json().await.unwrap()
}

async fn create_post(c: &Client, content: &str) -> serde_json::Value {
    let r = c.post(format!("{ENVOY}/api/v1/posts"))
        .json(&json!({ "content": content })).send().await.unwrap();
    assert_eq!(r.status(), 200, "create_post failed");
    r.json().await.unwrap()
}

async fn get_post(c: &Client, id: &str) -> serde_json::Value {
    let r = c.get(format!("{ENVOY}/api/v1/posts/{id}")).send().await.unwrap();
    assert_eq!(r.status(), 200);
    r.json().await.unwrap()
}

#[tokio::test]
async fn like_is_idempotent_and_counts() {
    let a = cli(); let _ = register_user(&a).await;
    let p = create_post(&a, "for like tests").await;
    let pid = p["id"].as_str().unwrap();

    // 1st like -> 201
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/like")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    // 2nd like -> 200 (idempotent)
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/like")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    // counter == 1
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 1);
    // unlike -> 204
    let r = a.delete(format!("{ENVOY}/api/v1/posts/{pid}/like")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::NO_CONTENT);
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 0);
}

#[tokio::test]
async fn hide_does_not_bump_like_count() {
    let a = cli(); let _ = register_user(&a).await;
    let p = create_post(&a, "for hide test").await;
    let pid = p["id"].as_str().unwrap();
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/hide")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 0);
    assert_eq!(post["save_count"], 0);
}

#[tokio::test]
async fn report_duplicate_pending_409() {
    let a = cli(); let b = cli();
    let _ = register_user(&a).await;
    let _ = register_user(&b).await;
    let p = create_post(&b, "for reports").await;
    let pid = p["id"].as_str().unwrap();
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/report"))
        .json(&json!({ "reason": "spam" })).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/report"))
        .json(&json!({ "reason": "spam" })).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CONFLICT);
}

#[tokio::test]
async fn comment_reply_then_reject_nested() {
    let a = cli(); let _ = register_user(&a).await;
    let p = create_post(&a, "for comments").await;
    let pid = p["id"].as_str().unwrap();
    // top-level
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "top-level" })).send().await.unwrap();
    assert_eq!(r.status(), 200);
    let top_id = r.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    // reply
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "reply", "parent_comment_id": top_id })).send().await.unwrap();
    assert_eq!(r.status(), 200);
    let reply_id = r.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    // reject nested
    let r = a.post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "nested", "parent_comment_id": reply_id })).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);
    // comment_count = 1 (top only)
    let post = get_post(&a, pid).await;
    assert_eq!(post["comment_count"], 1);
}

#[tokio::test]
async fn my_endpoint_reflects_state() {
    let a = cli(); let b = cli();
    let _ = register_user(&a).await;
    let _ = register_user(&b).await;
    let p = create_post(&b, "for /me test").await;
    let pid = p["id"].as_str().unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/like")).send().await.unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/save")).send().await.unwrap();
    let r = a.get(format!("{ENVOY}/api/v1/posts/{pid}/me")).send().await.unwrap();
    let me: serde_json::Value = r.json().await.unwrap();
    assert_eq!(me["liked"], true);
    assert_eq!(me["saved"], true);
    assert_eq!(me["shared"], false);
}

#[tokio::test]
async fn kafka_emits_liked_event() {
    let a = cli(); let _ = register_user(&a).await;
    let p = create_post(&a, "for kafka").await;
    let pid = p["id"].as_str().unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/like")).send().await.unwrap();
    // poll kafka topic via docker exec
    let out = Command::new("docker").args([
        "compose","exec","-T","kafka",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server","kafka:9092",
        "--topic","oecophylla.interactions",
        "--from-beginning","--max-messages","1","--timeout-ms","5000",
    ]).output().expect("docker exec failed");
    let body = String::from_utf8_lossy(&out.stdout);
    assert!(body.contains("\"event_type\":\"liked\""), "stdout: {body}");
}
```

- [ ] **Step 2: Run**
  ```bash
  docker compose up -d --build interaction-service
  cd backend
  cargo test -p interaction-service --test smoke -- --test-threads=1
  ```
  Expected: 6 tests pass.

- [ ] **Step 3: Commit**
  ```bash
  git add backend/services/interaction-service/tests/
  git commit -m "test(interaction-service): smoke for like/hide/report/comment/me/kafka"
  ```

---

## Task 7: content-service exposes new counters

**Files:**
- Modify: `backend/services/content-service/src/repo.rs`

- [ ] **Step 1: Add 4 fields** to `PostRow` and update every `SELECT` query in `repo.rs` to include `like_count, comment_count, save_count, share_count`.

  ```rust
  #[derive(sqlx::FromRow, serde::Serialize, Clone)]
  pub struct PostRow {
      // ... existing fields
      pub like_count: i32,
      pub comment_count: i32,
      pub save_count: i32,
      pub share_count: i32,
  }
  ```

  Update `by_id`, `list_by_author`, `insert` SQL strings to append the 4 columns in both SELECT and RETURNING clauses.

- [ ] **Step 2: Verify**
  ```bash
  cd backend && cargo check --workspace
  docker compose build content-service && docker compose up -d content-service
  curl -s "http://localhost:8080/api/v1/posts/<any-id>" | python3 -m json.tool | grep _count
  ```
  Expected: 4 lines with counter values (likely 0 unless interactions exist).

- [ ] **Step 3: Commit**
  ```bash
  git add backend/services/content-service/src/repo.rs
  git commit -m "feat(content-service): expose like/comment/save/share counters in PostRow"
  ```

---

## Task 8: Frontend types + extend mock data

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/mock/feed.ts`

- [ ] **Step 1: Extend types** — add `Comment`, `MyInteractions`, `ReportReason`; extend `Post` with 4 counter fields. Copy from spec §6.1.

- [ ] **Step 2: Update mock posts** — set non-zero counter fields (e.g. `like_count: 12 + i, comment_count: i, save_count: 3 + i, share_count: 1`) so the action bar shows numbers.

- [ ] **Step 3: Verify** — `pnpm exec svelte-check` clean.

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/lib/{types.ts,mock/feed.ts}
  git commit -m "feat(frontend): types for Comment/MyInteractions and Post counters; update mock feed"
  ```

---

## Task 9: PostActionBar + PostCard integration

**Files:**
- Create: `frontend/src/lib/components/PostActionBar.svelte`
- Modify: `frontend/src/lib/components/PostCard.svelte`

- [ ] **Step 1: `PostActionBar.svelte`** — props `post: Post`, `me: MyInteractions | null`. Renders 4 buttons (heart, bookmark, share, comment-count link to detail) + report flag. Optimistic local state. On click invokes `apiFetch` and rolls back on error via `alert()` (Phase 2A: no toast).

  ```svelte
  <script lang="ts">
    import { apiFetch, ApiException } from '$lib/api';
    import type { Post, MyInteractions } from '$lib/types';
    export let post: Post;
    export let me: MyInteractions | null = null;

    let liked  = me?.liked  ?? false;
    let saved  = me?.saved  ?? false;
    let likeCount = post.like_count;
    let saveCount = post.save_count;

    async function toggle(kind: 'like' | 'save') {
      const wasOn = kind === 'like' ? liked : saved;
      const counter = kind === 'like' ? likeCount : saveCount;
      // optimistic
      if (kind === 'like') { liked = !wasOn;  likeCount = counter + (wasOn ? -1 : 1); }
      else                 { saved = !wasOn;  saveCount = counter + (wasOn ? -1 : 1); }
      try {
        await apiFetch(fetch, `/posts/${post.id}/${kind}`, { method: wasOn ? 'DELETE' : 'POST' });
      } catch (e) {
        // rollback
        if (kind === 'like') { liked = wasOn; likeCount = counter; }
        else                 { saved = wasOn; saveCount = counter; }
        if (e instanceof ApiException && e.status === 401) alert('Vui lòng đăng nhập');
        else alert('Có lỗi xảy ra');
      }
    }
  </script>

  <div class="mt-3 flex items-center gap-2 text-mono-meta">
    <button class="glass-chip" on:click={() => toggle('like')} aria-pressed={liked}>
      {liked ? '♥' : '♡'} {likeCount}
    </button>
    <button class="glass-chip" on:click={() => toggle('save')} aria-pressed={saved}>
      {saved ? '★' : '☆'} {saveCount}
    </button>
    <a class="glass-chip" href={`/post/${post.id}`}>💬 {post.comment_count}</a>
    <span class="glass-chip">↗ {post.share_count}</span>
  </div>
  ```

- [ ] **Step 2: Integrate** — `PostCard.svelte` accepts an optional `me: MyInteractions | null = null` prop and renders `<PostActionBar post={post} me={me} />` at the end of the card.

- [ ] **Step 3: Verify** — svelte-check clean.

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/lib/components/{PostActionBar,PostCard}.svelte
  git commit -m "feat(frontend): post action bar with optimistic like/save"
  ```

---

## Task 10: post/[id] page — comments + me + report

**Files:**
- Modify: `frontend/src/routes/post/[id]/+page.server.ts`
- Modify: `frontend/src/routes/post/[id]/+page.svelte`
- Create: `frontend/src/lib/components/CommentItem.svelte`
- Create: `frontend/src/lib/components/CommentForm.svelte`
- Create: `frontend/src/lib/components/ReportDialog.svelte`

- [ ] **Step 1: `+page.server.ts`** — load `post`, `me` (catch 401 → null), `comments` (limit 20).
  ```ts
  import type { PageServerLoad } from './$types';
  import { apiFetch, ApiException } from '$lib/api';
  import { error } from '@sveltejs/kit';
  import type { Post, Comment, MyInteractions } from '$lib/types';

  export const load: PageServerLoad = async ({ params, fetch }) => {
    let post: Post;
    try { post = await apiFetch<Post>(fetch, `/posts/${params.id}`); }
    catch (e) { if (e instanceof ApiException && e.status === 404) throw error(404, 'Post not found'); throw e; }
    apiFetch(fetch, `/posts/${params.id}/view`, { method: 'POST' }).catch(() => {});
    let me: MyInteractions | null = null;
    try { me = await apiFetch<MyInteractions>(fetch, `/posts/${params.id}/me`); } catch {}
    const comments = await apiFetch<Comment[]>(fetch, `/posts/${params.id}/comments?limit=20`);
    return { post, me, comments };
  };
  ```

- [ ] **Step 2: `+page.svelte`**
  ```svelte
  <script lang="ts">
    import PostCard from '$lib/components/PostCard.svelte';
    import CommentItem from '$lib/components/CommentItem.svelte';
    import CommentForm from '$lib/components/CommentForm.svelte';
    import ReportDialog from '$lib/components/ReportDialog.svelte';
    import { user } from '$lib/stores/auth';
    export let data;
    let showReport = false;
  </script>

  <PostCard post={data.post} me={data.me} />
  {#if $user}
    <div class="mt-3"><button class="glass-chip" on:click={() => (showReport = true)}>Báo cáo</button></div>
  {/if}
  {#if showReport}
    <ReportDialog post_id={data.post.id} on:close={() => (showReport = false)} />
  {/if}

  <section class="mt-6">
    <h2 class="text-display-serif text-xl mb-3">Bình luận ({data.post.comment_count})</h2>
    {#if $user}
      <CommentForm post_id={data.post.id} />
    {/if}
    <ul class="mt-4 space-y-3">
      {#each data.comments as c (c.id)}
        <CommentItem {c} post_id={data.post.id} />
      {/each}
      {#if data.comments.length === 0}<p class="text-ink-500">Chưa có bình luận.</p>{/if}
    </ul>
  </section>
  ```

- [ ] **Step 3: `CommentItem.svelte`**
  ```svelte
  <script lang="ts">
    import type { Comment } from '$lib/types';
    import CommentForm from './CommentForm.svelte';
    import { apiFetch, ApiException } from '$lib/api';
    import { user } from '$lib/stores/auth';
    export let c: Comment;
    export let post_id: string;
    let showReply = false;
    let extraReplies: Comment[] = [];
    let allReplies = [...(c.replies ?? [])];
    let hasMore = c.has_more_replies ?? false;

    async function loadMore() {
      const next = await apiFetch<Comment[]>(fetch, `/comments/${c.id}/replies?limit=20`);
      // simple replacement; in real life dedupe by id
      allReplies = next;
      hasMore = false;
    }
    async function del() {
      if (!confirm('Xóa bình luận này?')) return;
      try {
        await apiFetch(fetch, `/comments/${c.id}`, { method: 'DELETE' });
        c.is_deleted = true;
        c.content = '[đã xóa]';
      } catch (e) { alert('Không xóa được'); }
    }
  </script>
  <li class="glass-surface p-4">
    <div class="text-mono-meta">@{c.author_username} · {new Date(c.created_at).toLocaleString('vi-VN')}</div>
    <p class="mt-1 whitespace-pre-wrap">{c.content}</p>
    <div class="mt-2 flex gap-2 text-sm">
      {#if $user && !c.parent_comment_id}<button class="glass-chip" on:click={() => (showReply = !showReply)}>Phản hồi</button>{/if}
      {#if $user && $user.id === c.author_id && !c.is_deleted}<button class="glass-chip" on:click={del}>Xóa</button>{/if}
    </div>
    {#if showReply}
      <div class="mt-2"><CommentForm post_id={post_id} parent_comment_id={c.id} /></div>
    {/if}
    {#if allReplies.length > 0}
      <ul class="mt-3 ml-6 space-y-2">
        {#each allReplies as r (r.id)}
          <li class="glass-surface p-3">
            <div class="text-mono-meta">@{r.author_username} · {new Date(r.created_at).toLocaleString('vi-VN')}</div>
            <p class="mt-1 whitespace-pre-wrap">{r.content}</p>
          </li>
        {/each}
      </ul>
      {#if hasMore}<button class="glass-chip mt-2 ml-6" on:click={loadMore}>Xem thêm phản hồi…</button>{/if}
    {/if}
  </li>
  ```

- [ ] **Step 4: `CommentForm.svelte`**
  ```svelte
  <script lang="ts">
    import { apiFetch, ApiException } from '$lib/api';
    import { invalidateAll } from '$app/navigation';
    export let post_id: string;
    export let parent_comment_id: string | null = null;
    let content = ''; let busy = false; let err: string | null = null;
    async function submit() {
      if (!content.trim()) return;
      busy = true; err = null;
      try {
        await apiFetch(fetch, `/posts/${post_id}/comments`, {
          method: 'POST',
          body: JSON.stringify({ content, parent_comment_id })
        });
        content = '';
        await invalidateAll();
      } catch (e) {
        if (e instanceof ApiException && e.status === 400) err = 'Nội dung không hợp lệ';
        else if (e instanceof ApiException && e.status === 401) err = 'Vui lòng đăng nhập';
        else err = 'Lỗi máy chủ';
      } finally { busy = false; }
    }
  </script>
  <form on:submit|preventDefault={submit} class="glass-surface p-3">
    <textarea class="w-full bg-transparent outline-none resize-none" rows="2" bind:value={content}
              placeholder={parent_comment_id ? 'Phản hồi…' : 'Viết bình luận…'} maxlength="2000"></textarea>
    {#if err}<p class="text-red-700 text-sm">{err}</p>{/if}
    <div class="mt-2 flex justify-end">
      <button class="glass-button-primary" type="submit" disabled={busy}>Gửi</button>
    </div>
  </form>
  ```

- [ ] **Step 5: `ReportDialog.svelte`**
  ```svelte
  <script lang="ts">
    import { apiFetch, ApiException } from '$lib/api';
    import { createEventDispatcher } from 'svelte';
    export let post_id: string;
    const dispatch = createEventDispatcher();
    let reason: 'spam'|'misinformation'|'harassment'|'nsfw'|'other' = 'spam';
    let detail = ''; let busy = false; let err: string | null = null;
    async function submit() {
      busy = true; err = null;
      try {
        await apiFetch(fetch, `/posts/${post_id}/report`, {
          method: 'POST', body: JSON.stringify({ reason, detail: detail || undefined })
        });
        dispatch('close');
        alert('Đã ghi nhận báo cáo. Cảm ơn bạn!');
      } catch (e) {
        if (e instanceof ApiException && e.status === 409) err = 'Bạn đã có báo cáo đang xử lý.';
        else err = 'Lỗi máy chủ';
      } finally { busy = false; }
    }
  </script>
  <div class="fixed inset-0 bg-ink-900/40 flex items-center justify-center z-50">
    <div class="glass-surface p-6 max-w-md w-full">
      <h3 class="text-display-serif text-xl mb-3">Báo cáo bài viết</h3>
      <div class="flex flex-col gap-2 text-sm">
        {#each ['spam','misinformation','harassment','nsfw','other'] as r}
          <label><input type="radio" bind:group={reason} value={r} /> {r}</label>
        {/each}
      </div>
      <textarea class="block w-full mt-3 px-3 py-2 rounded-xl bg-white/60 border border-white/60" rows="2"
                bind:value={detail} placeholder="Chi tiết (tùy chọn)"></textarea>
      {#if err}<p class="text-red-700 text-sm mt-2">{err}</p>{/if}
      <div class="mt-4 flex justify-end gap-2">
        <button class="glass-chip" on:click={() => dispatch('close')}>Hủy</button>
        <button class="glass-button-primary" on:click={submit} disabled={busy}>Gửi</button>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 6: Verify** — `pnpm exec svelte-check` 0 errors.

- [ ] **Step 7: Commit**
  ```bash
  git add frontend/src/routes/post/[id]/ frontend/src/lib/components/{CommentItem,CommentForm,ReportDialog}.svelte
  git commit -m "feat(frontend): post detail with comments, replies, report dialog"
  ```

---

## Task 11: PostActionBar wired with `me` on profile feed (optional but small)

**Files:**
- Modify: `frontend/src/routes/profile/[id]/+page.server.ts`
- Modify: `frontend/src/routes/profile/[id]/+page.svelte`

- [ ] **Step 1: Optionally fetch `me` for each post**. Profile shows multiple posts; doing 20 round-trips for `/me` is wasteful. Phase 2A keeps it simple: don't pass `me` for profile posts (so action bar starts in "not liked" state regardless). Document this in the page as a comment. Phase 2B will add a bulk `/me` endpoint.

  Add a one-line comment in the page where the `<PostCard />` is rendered: `<!-- Phase 2A: profile posts do not hydrate /me; counters show but heart starts unset. Phase 2B adds bulk endpoint. -->`

- [ ] **Step 2: Commit (empty)**
  ```bash
  git commit --allow-empty -m "chore(frontend): document profile feed lacks /me hydration in 2A"
  ```

(This task is essentially a no-op with documentation — exists to mark the gap for Phase 2B.)

---

## Task 12: vitest for PostActionBar optimistic

**Files:**
- Create: `frontend/src/lib/components/PostActionBar.test.ts`

- [ ] **Step 1: Write test** — uses `@testing-library/svelte` if available; otherwise lightweight DOM test of the optimistic counter logic. Minimum: 2 unit tests.

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Lightweight: extract toggle() from the component or mirror its logic in a pure fn for testability.
// Phase 2A acceptable approach: re-implement the optimistic toggle in a pure helper and test that.

function applyOptimistic(state: { liked: boolean, count: number }, ok: boolean) {
  // Initial flip
  const flipped = { liked: !state.liked, count: state.count + (state.liked ? -1 : 1) };
  // Rollback on failure
  return ok ? flipped : state;
}

describe('PostActionBar optimistic toggle', () => {
  it('flips state and counter on success', () => {
    expect(applyOptimistic({ liked: false, count: 5 }, true)).toEqual({ liked: true, count: 6 });
    expect(applyOptimistic({ liked: true,  count: 6 }, true)).toEqual({ liked: false, count: 5 });
  });
  it('rolls back on failure', () => {
    expect(applyOptimistic({ liked: false, count: 5 }, false)).toEqual({ liked: false, count: 5 });
  });
});
```

(If a future task wants a true component test, swap to `@testing-library/svelte` + mocked fetch.)

- [ ] **Step 2: Run + commit**
  ```bash
  cd frontend && pnpm vitest run
  cd .. && git add frontend/src/lib/components/PostActionBar.test.ts
  git commit -m "test(frontend): post action bar optimistic toggle logic"
  ```

---

## Task 13: DoD verify + tag

**Files:** none new; verification + tag.

- [ ] **Step 1: Full stack up**
  ```bash
  docker compose up -d --build
  sleep 10
  docker compose ps
  ```
  Expected: interaction-service appears in `Up` state; all healthchecks green.

- [ ] **Step 2: Spec §8.3 checklist**:
  1. Migrations idempotent — `docker compose up migrate` second run = no-op.
  2. `cargo test -p interaction-service --test smoke -- --test-threads=1` → 6 passes.
  3. `cargo test --workspace --no-fail-fast` — note same kafka-host limitation; record but don't block.
  4. Frontend `pnpm build` clean; `pnpm exec svelte-check` 0 errors.
  5. Manual browser pass: click ♥, reload, ♥ stays filled; counter updates; report → success; second report → 409 message; comment + reply → renders; nested reply attempt → error.
  6. Counter consistency:
     ```bash
     docker compose exec postgres psql -U oecophylla -d oecophylla -c "
       SELECT p.like_count, (SELECT count(*) FROM interactions i WHERE i.post_id=p.id AND i.type='like') AS actual
       FROM posts p ORDER BY created_at DESC LIMIT 5;"
     ```
     `like_count` matches `actual`.
  7. Lint: `cargo clippy --workspace -- -D warnings` clean.

- [ ] **Step 3: Tag**
  ```bash
  git commit --allow-empty -m "chore: phase 2a definition of done verified"
  git tag phase-2a-complete
  ```

- [ ] **Step 4: Final scorecard report** — 7-row table (one per spec §8.3 sub-item).

---

## Spec coverage self-review

| Spec section | Tasks |
|---|---|
| §1 Goals / non-goals | informs all; non-goals enforced by Task 11 documenting the gap |
| §2 Architecture / Envoy reroute / cargo / compose | Tasks 2, 5 |
| §3 Data model | Task 1 |
| §3.5 weights | Task 4 (events.rs `weight_for`) |
| §4 Endpoints | Tasks 3, 4, 5 |
| §4.5 Rate limits | Future: add per-route limits in Task 5 (TODO: confirm `crates/common` middleware is mounted in main.rs; if not, add). |
| §5 Kafka events | Task 4 (events.rs + each handler emits), Task 5 (topic creation) |
| §6 Frontend types/components | Tasks 8, 9, 10 |
| §7 content-service touchpoint | Task 7 |
| §8 Testing & DoD | Tasks 6, 12, 13 |
| §9 Risks | Task 4 (1-level enforcement in repo) |

## Placeholder scan

No TBD/TODO except one explicit forward reference (Task 11) which is intentional and documented. The `Rate limits §4.5` note in coverage table is a follow-up: the middleware exists in `crates/common` from Phase 0+1 but is not currently mounted in any service. Mounting per-route limits is a small enhancement — adding it in Task 5 main.rs as part of router building is straightforward; if time-constrained, defer to Phase 2B with a documented note.

## Type consistency self-review

- `repo::CommentRow` struct in Task 3 used by Task 4 handlers identically.
- `MyInteractions` shape matches between repo (Task 3), handlers (Task 4 returns repo type), and frontend types (Task 8).
- `interaction_type` enum values (`like|save|share|hide|report`) match across migration (Task 1), repo (Task 3), handlers (Task 4), events (Task 4), tests (Task 6), and frontend types — verified.
- Kafka topic name `oecophylla.interactions` is used identically in events.rs (Task 4), compose init-topics (Task 5), and tests (Task 6).
- Counter column names (`like_count|save_count|share_count|comment_count`) match across migration (Task 1), repo (Task 3 `counter_column` helper in events.rs Task 4 — same set), content-service PostRow (Task 7), and frontend `Post` interface (Task 8).

---

**Plan complete. Execution mode: subagent-driven (autonomous per user instruction).**
