# Axum + PostgreSQL Base Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable Axum + PostgreSQL service in `/Users/nhathaminh/oecophylla/backend` with a bind-mounted dev container, live reload via `cargo-watch`, auto-applied migrations, and a worked end-to-end CRUD example (`items`).

**Architecture:** Single Rust binary built on `axum 0.8` + `sqlx 0.8` (Postgres, rustls, runtime `query_as` — no compile-time macros). Modules: `config`, `state`, `error`, `routes/{health,items}`, `db/items`. `main` boots tracing, builds the `PgPool`, runs embedded migrations, mounts the router with `TraceLayer`, and serves on `0.0.0.0:$APP_PORT`. Docker Compose runs Postgres 16 alongside the app container, with `.:/app` bind-mounted plus named volumes for `target/` and the cargo registry to keep rebuilds fast.

**Tech Stack:** Rust 1.x, Axum 0.8, Tokio, sqlx 0.8 (postgres + rustls), tower-http (TraceLayer), tracing/tracing-subscriber, figment + dotenvy, thiserror + anyhow, uuid, chrono, serde, Docker Compose v2, Postgres 16, cargo-watch.

**Spec:** `docs/superpowers/specs/2026-05-24-axum-postgres-base-template-design.md`

---

## How to verify each task

This template's "tests" are layered:

- **`cargo check`** on the host (Rust toolchain only, no DB needed) — fast, runs after every code-touching task. This is the primary inner-loop signal.
- **`docker compose up --build`** + `curl` — the integration test in Task 14. The full CRUD cycle is the acceptance gate.

Engineers without `cargo` locally can substitute `docker run --rm -v "$PWD":/app -w /app rust:1-bookworm cargo check` where the plan says `cargo check`.

---

### Task 1: Initialize git repo, cargo binary crate, and ignore files

**Files:**
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `Cargo.toml` (via `cargo init`)
- Create: `src/main.rs` (via `cargo init`, will be overwritten in Task 9)

- [ ] **Step 1: Initialize git**

```bash
cd /Users/nhathaminh/oecophylla/backend
git init
```

Expected output: `Initialized empty Git repository in /Users/nhathaminh/oecophylla/backend/.git/`.

- [ ] **Step 2: Initialize the cargo binary crate**

```bash
cd /Users/nhathaminh/oecophylla/backend
cargo init --name backend --bin .
```

Expected output: `Created binary (application) package`. This creates `Cargo.toml` and `src/main.rs` (default "Hello, world!"). Do not edit them yet.

- [ ] **Step 3: Write `.gitignore`**

```gitignore
/target
**/*.rs.bk
Cargo.lock.bak

.env
.env.local

.DS_Store
.idea/
.vscode/

.remember/
```

Note: `Cargo.lock` is intentionally tracked because this is a binary crate.

- [ ] **Step 4: Write `.dockerignore`**

```dockerignore
target
.git
.gitignore
.idea
.vscode
.DS_Store
.env
.env.local
.remember
docs
*.md
```

- [ ] **Step 5: Verify the default crate compiles**

Run: `cargo check`
Expected: `Finished` with no errors. (Downloads the index on first run; that's fine.)

- [ ] **Step 6: Commit**

```bash
git add .gitignore .dockerignore Cargo.toml Cargo.lock src/main.rs
git commit -m "chore: init cargo binary crate and ignore files"
```

---

### Task 2: Declare all production dependencies

**Files:**
- Modify: `Cargo.toml`

- [ ] **Step 1: Replace `Cargo.toml` with the full dependency set**

Overwrite `Cargo.toml` with:

```toml
[package]
name = "backend"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.8"
tokio = { version = "1", features = ["full"] }
tower-http = { version = "0.6", features = ["trace"] }

sqlx = { version = "0.8", default-features = false, features = [
    "runtime-tokio",
    "tls-rustls-ring-webpki",
    "postgres",
    "uuid",
    "chrono",
    "migrate",
] }

serde = { version = "1", features = ["derive"] }
serde_json = "1"

tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

figment = { version = "0.10", features = ["env"] }
dotenvy = "0.15"

thiserror = "1"
anyhow = "1"

uuid = { version = "1", features = ["v7", "serde"] }
chrono = { version = "0.4", default-features = false, features = ["clock", "serde"] }
```

- [ ] **Step 2: Verify dependencies resolve and compile**

Run: `cargo check`
Expected: `Finished` after downloading and building dependencies (takes several minutes on a cold cache; that's normal).

- [ ] **Step 3: Commit**

```bash
git add Cargo.toml Cargo.lock
git commit -m "chore: add axum, sqlx, tracing, and supporting deps"
```

---

### Task 3: Write `.env.example` and the initial migration

**Files:**
- Create: `.env.example`
- Create: `migrations/20260524000001_init_items.sql`

- [ ] **Step 1: Write `.env.example`**

```env
DATABASE_URL=postgres://app:app@localhost:5432/app
APP_PORT=3000
DB_MAX_CONNECTIONS=10
RUST_LOG=info,backend=debug
```

- [ ] **Step 2: Write the initial migration**

Create `migrations/20260524000001_init_items.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 3: Commit**

```bash
git add .env.example migrations/
git commit -m "chore: add env example and items table migration"
```

---

### Task 4: Implement `src/config.rs`

**Files:**
- Create: `src/config.rs`

This module owns env parsing. No HTTP, no SQL knowledge.

- [ ] **Step 1: Write `src/config.rs`**

```rust
use figment::{providers::Env, Figment};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct AppConfig {
    pub database_url: String,
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default = "default_max_connections")]
    pub db_max_connections: u32,
}

fn default_port() -> u16 {
    3000
}

fn default_max_connections() -> u32 {
    10
}

impl AppConfig {
    pub fn from_env() -> Result<Self, figment::Error> {
        Figment::new().merge(Env::raw()).extract()
    }
}
```

- [ ] **Step 2: Add the module to `src/main.rs` so `cargo check` exercises it**

Replace `src/main.rs` with:

```rust
mod config;

fn main() {
    let _ = config::AppConfig::from_env();
}
```

- [ ] **Step 3: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/config.rs src/main.rs
git commit -m "feat: add AppConfig with env-based loading"
```

---

### Task 5: Implement `src/state.rs`

**Files:**
- Create: `src/state.rs`

- [ ] **Step 1: Write `src/state.rs`**

```rust
use sqlx::PgPool;

#[derive(Clone)]
pub struct AppState {
    pub pool: PgPool,
}
```

- [ ] **Step 2: Reference it from `src/main.rs`**

Replace `src/main.rs` with:

```rust
mod config;
mod state;

fn main() {
    let _ = config::AppConfig::from_env();
}
```

- [ ] **Step 3: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/state.rs src/main.rs
git commit -m "feat: add AppState wrapping PgPool"
```

---

### Task 6: Implement `src/error.rs`

**Files:**
- Create: `src/error.rs`

This module defines `AppError` and its `IntoResponse` mapping. Handlers return `Result<T, AppError>`.

- [ ] **Step 1: Write `src/error.rs`**

```rust
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("not found")]
    NotFound,

    #[error("bad request: {0}")]
    BadRequest(String),

    #[error("conflict: {0}")]
    Conflict(String),

    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => AppError::NotFound,
            other => AppError::Internal(anyhow::Error::new(other)),
        }
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound => (StatusCode::NOT_FOUND, "not found".to_string()),
            AppError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg.clone()),
            AppError::Conflict(msg) => (StatusCode::CONFLICT, msg.clone()),
            AppError::Internal(err) => {
                tracing::error!(error = ?err, "internal error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "internal server error".to_string(),
                )
            }
        };

        (status, Json(json!({ "error": message }))).into_response()
    }
}

pub type AppResult<T> = Result<T, AppError>;
```

- [ ] **Step 2: Wire the module into `src/main.rs`**

Replace `src/main.rs` with:

```rust
mod config;
mod error;
mod state;

fn main() {
    let _ = config::AppConfig::from_env();
}
```

- [ ] **Step 3: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/error.rs src/main.rs
git commit -m "feat: add AppError with IntoResponse mapping"
```

---

### Task 7: Implement `src/db/items.rs`

**Files:**
- Create: `src/db/mod.rs`
- Create: `src/db/items.rs`

This module owns all SQL for `items`. Functions take `&PgPool` and typed inputs, return typed outputs or `sqlx::Error`. No HTTP knowledge.

- [ ] **Step 1: Write `src/db/mod.rs`**

```rust
pub mod items;
```

- [ ] **Step 2: Write `src/db/items.rs`**

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, sqlx::FromRow)]
pub struct Item {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct ItemInput {
    pub name: String,
    pub description: Option<String>,
}

pub async fn list(pool: &PgPool) -> Result<Vec<Item>, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "SELECT id, name, description, created_at, updated_at \
         FROM items ORDER BY created_at DESC",
    )
    .fetch_all(pool)
    .await
}

pub async fn create(pool: &PgPool, input: &ItemInput) -> Result<Item, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "INSERT INTO items (name, description) \
         VALUES ($1, $2) \
         RETURNING id, name, description, created_at, updated_at",
    )
    .bind(&input.name)
    .bind(&input.description)
    .fetch_one(pool)
    .await
}

pub async fn get(pool: &PgPool, id: Uuid) -> Result<Item, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "SELECT id, name, description, created_at, updated_at \
         FROM items WHERE id = $1",
    )
    .bind(id)
    .fetch_one(pool)
    .await
}

pub async fn update(pool: &PgPool, id: Uuid, input: &ItemInput) -> Result<Item, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "UPDATE items \
         SET name = $2, description = $3, updated_at = now() \
         WHERE id = $1 \
         RETURNING id, name, description, created_at, updated_at",
    )
    .bind(id)
    .bind(&input.name)
    .bind(&input.description)
    .fetch_one(pool)
    .await
}

pub async fn delete(pool: &PgPool, id: Uuid) -> Result<(), sqlx::Error> {
    let result = sqlx::query("DELETE FROM items WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await?;

    if result.rows_affected() == 0 {
        return Err(sqlx::Error::RowNotFound);
    }
    Ok(())
}
```

- [ ] **Step 3: Wire the module into `src/main.rs`**

Replace `src/main.rs` with:

```rust
mod config;
mod db;
mod error;
mod state;

fn main() {
    let _ = config::AppConfig::from_env();
}
```

- [ ] **Step 4: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/db/ src/main.rs
git commit -m "feat: add db::items CRUD query functions"
```

---

### Task 8: Implement `src/routes/health.rs`

**Files:**
- Create: `src/routes/mod.rs`
- Create: `src/routes/health.rs`

- [ ] **Step 1: Write `src/routes/mod.rs`**

```rust
pub mod health;
pub mod items;
```

(`items` is referenced ahead of Task 9 so we only edit this file once. `cargo check` will fail at the end of Step 4 until Task 9 lands — that's expected. To keep this task green on its own, temporarily comment out `pub mod items;` and uncomment it in Task 9.)

For this task, start with the temporary version:

```rust
pub mod health;
// pub mod items; // enabled in Task 9
```

- [ ] **Step 2: Write `src/routes/health.rs`**

```rust
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::json;
use sqlx::Executor;

use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new().route("/health", get(health))
}

async fn health(State(state): State<AppState>) -> impl IntoResponse {
    match state.pool.execute("SELECT 1").await {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "status": "ok", "db": "ok" })),
        ),
        Err(err) => {
            tracing::warn!(error = ?err, "health check db ping failed");
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "status": "degraded", "db": "down" })),
            )
        }
    }
}
```

- [ ] **Step 3: Wire `routes` into `src/main.rs`**

Replace `src/main.rs` with:

```rust
mod config;
mod db;
mod error;
mod routes;
mod state;

fn main() {
    let _ = config::AppConfig::from_env();
}
```

- [ ] **Step 4: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/routes/ src/main.rs
git commit -m "feat: add /health route with DB ping"
```

---

### Task 9: Implement `src/routes/items.rs`

**Files:**
- Create: `src/routes/items.rs`
- Modify: `src/routes/mod.rs`

- [ ] **Step 1: Write `src/routes/items.rs`**

```rust
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use uuid::Uuid;

use crate::db::items::{self, Item, ItemInput};
use crate::error::AppResult;
use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(list).post(create))
        .route("/{id}", get(get_one).put(update).delete(delete))
}

async fn list(State(state): State<AppState>) -> AppResult<Json<Vec<Item>>> {
    let rows = items::list(&state.pool).await?;
    Ok(Json(rows))
}

async fn create(
    State(state): State<AppState>,
    Json(input): Json<ItemInput>,
) -> AppResult<impl IntoResponse> {
    let item = items::create(&state.pool, &input).await?;
    Ok((StatusCode::CREATED, Json(item)))
}

async fn get_one(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<Json<Item>> {
    let item = items::get(&state.pool, id).await?;
    Ok(Json(item))
}

async fn update(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(input): Json<ItemInput>,
) -> AppResult<Json<Item>> {
    let item = items::update(&state.pool, id, &input).await?;
    Ok(Json(item))
}

async fn delete(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<StatusCode> {
    items::delete(&state.pool, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
```

- [ ] **Step 2: Enable the `items` module in `src/routes/mod.rs`**

Overwrite `src/routes/mod.rs` with:

```rust
pub mod health;
pub mod items;
```

- [ ] **Step 3: Verify**

Run: `cargo check`
Expected: `Finished` with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/routes/
git commit -m "feat: add /items CRUD routes"
```

---

### Task 10: Implement `src/main.rs` boot sequence

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Overwrite `src/main.rs` with the full boot sequence**

```rust
mod config;
mod db;
mod error;
mod routes;
mod state;

use std::net::SocketAddr;

use anyhow::Context;
use axum::Router;
use sqlx::postgres::PgPoolOptions;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;
use tracing_subscriber::EnvFilter;

use crate::config::AppConfig;
use crate::state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let _ = dotenvy::dotenv();

    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info,backend=debug")),
        )
        .init();

    let cfg = AppConfig::from_env().context("failed to load AppConfig from environment")?;

    let pool = PgPoolOptions::new()
        .max_connections(cfg.db_max_connections)
        .connect(&cfg.database_url)
        .await
        .context("failed to connect to Postgres")?;

    sqlx::migrate!("./migrations")
        .run(&pool)
        .await
        .context("failed to run database migrations")?;

    let state = AppState { pool };

    let app: Router = Router::new()
        .merge(routes::health::router())
        .nest("/items", routes::items::router())
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], cfg.port));
    tracing::info!(%addr, "listening");

    let listener = TcpListener::bind(addr).await.context("failed to bind TCP listener")?;
    axum::serve(listener, app).await.context("server error")?;

    Ok(())
}
```

- [ ] **Step 2: Verify**

Run: `cargo check`
Expected: `Finished` with no errors. (`cargo build --release` is intentionally not required here; release builds happen via compose.)

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: wire boot sequence — tracing, pool, migrations, router, serve"
```

---

### Task 11: Write the dev `Dockerfile`

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM rust:1-bookworm

RUN cargo install cargo-watch --locked \
 && cargo install sqlx-cli --no-default-features --features rustls,postgres --locked

WORKDIR /app

EXPOSE 3000

CMD ["cargo", "watch", "-q", "-c", "-w", "src", "-w", "Cargo.toml", "-w", "migrations", "-x", "run"]
```

- [ ] **Step 2: Verify the Dockerfile builds**

Run: `docker build -t backend-dev:test .`
Expected: image builds successfully. The image is large (~2GB) because it includes the full Rust toolchain plus `cargo-watch` and `sqlx-cli` — that is acceptable for a dev image.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "chore: add dev Dockerfile with cargo-watch and sqlx-cli"
```

---

### Task 12: Write `compose.yaml`

**Files:**
- Create: `compose.yaml`

- [ ] **Step 1: Write `compose.yaml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 2s
      timeout: 2s
      retries: 20

  app:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgres://app:app@db:5432/app
      APP_PORT: "3000"
      DB_MAX_CONNECTIONS: "10"
      RUST_LOG: info,backend=debug
    ports:
      - "3000:3000"
    volumes:
      - .:/app
      - cargo-registry:/usr/local/cargo/registry
      - cargo-git:/usr/local/cargo/git
      - target-cache:/app/target

volumes:
  pgdata:
  cargo-registry:
  cargo-git:
  target-cache:
```

- [ ] **Step 2: Validate compose syntax**

Run: `docker compose config`
Expected: prints the resolved compose file with no error.

- [ ] **Step 3: Commit**

```bash
git add compose.yaml
git commit -m "chore: add docker compose with postgres and bind-mounted dev app"
```

---

### Task 13: Smoke test — bring the stack up and run the CRUD cycle

This is the integration test. No code changes; just verify acceptance criteria.

- [ ] **Step 1: Bring the stack up in the background**

Run: `docker compose up -d --build`
Expected: both services start. `docker compose ps` shows `db` healthy and `app` running.

- [ ] **Step 2: Tail app logs and confirm boot succeeded**

Run: `docker compose logs app | tail -n 50`
Expected: lines indicating sqlx applied the migration and a line containing `listening` with `addr=0.0.0.0:3000`. If you see migration errors, stop here and debug — the app should fail fast.

- [ ] **Step 3: Hit the health endpoint**

Run: `curl -i http://localhost:3000/health`
Expected: HTTP/1.1 200, body `{"db":"ok","status":"ok"}` (key order may differ).

- [ ] **Step 4: Create an item**

Run:

```bash
curl -i -X POST http://localhost:3000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"first","description":"hello"}'
```

Expected: HTTP/1.1 201, body containing an `Item` with `id` (UUID), `name: "first"`, `description: "hello"`, and timestamps.

Capture the `id` for the next steps. Example: `export ITEM_ID=<id from response>`.

- [ ] **Step 5: List items**

Run: `curl -s http://localhost:3000/items | head`
Expected: a JSON array containing the item created in Step 4.

- [ ] **Step 6: Get the item by id**

Run: `curl -i http://localhost:3000/items/$ITEM_ID`
Expected: HTTP/1.1 200, body matches the created item.

- [ ] **Step 7: Update the item**

Run:

```bash
curl -i -X PUT http://localhost:3000/items/$ITEM_ID \
  -H 'Content-Type: application/json' \
  -d '{"name":"first-updated","description":null}'
```

Expected: HTTP/1.1 200, body shows `name: "first-updated"`, `description: null`, and `updated_at` is later than `created_at`.

- [ ] **Step 8: Delete the item**

Run: `curl -i -X DELETE http://localhost:3000/items/$ITEM_ID`
Expected: HTTP/1.1 204, no body.

- [ ] **Step 9: Confirm the item is gone**

Run: `curl -i http://localhost:3000/items/$ITEM_ID`
Expected: HTTP/1.1 404, body `{"error":"not found"}`.

- [ ] **Step 10: Confirm live reload works**

Edit `src/routes/health.rs` and change the success message to `"db": "ok!"`. Save the file.

Run: `docker compose logs -f app` and wait for `cargo-watch` to rebuild (a few seconds).

Then run: `curl -s http://localhost:3000/health`
Expected: `{"status":"ok","db":"ok!"}` — proving the bind mount + cargo-watch loop works.

Revert the change before committing.

- [ ] **Step 11: Bring the stack down**

Run: `docker compose down`
Expected: both containers stop and are removed. Named volumes persist (so `pgdata` and caches survive across runs).

- [ ] **Step 12: Confirm host-side `cargo build` works without a running DB**

Run: `docker compose down && cargo build`
Expected: `Finished` with no errors — proves no compile-time DB dependency.

- [ ] **Step 13: Commit nothing (this task is verification only)**

No commit. If any step failed, fix the underlying code in the appropriate earlier task's files and re-run from Step 1.

---

## Self-review notes

- **Spec coverage:** Stack/versions (Task 2), layout (Tasks 4–10), endpoints (Tasks 8–9), migration (Task 3), boot sequence (Task 10), config defaults (Task 4), error mapping (Task 6), compose with named volumes (Task 12), dev Dockerfile (Task 11), all acceptance criteria (Task 13 steps 2, 3, 4–9, 10, 12).
- **Out-of-scope items in the spec** (prod Dockerfile, auth, pagination, OpenAPI, integration test harness, CI, metrics, manual migration deploy) are intentionally not in the plan.
- **No placeholders:** every code step has the full file contents. The one "stub-then-replace" pattern (Task 8 commenting `items` then Task 9 uncommenting it) keeps each task's `cargo check` green.
- **Type consistency:** `Item`, `ItemInput`, `items::list/create/get/update/delete`, `AppError`, `AppResult`, `AppState { pool }` are referenced identically across Tasks 6–10.
