# Axum + PostgreSQL Base Template — Design

**Date:** 2026-05-24
**Status:** Draft, awaiting user review
**Working directory:** `/Users/nhathaminh/oecophylla/backend`

## Purpose

Bootstrap a runnable Axum service in a previously empty backend directory. The output must be a developer-friendly base template:

- Single `docker compose up` brings the whole stack online: Postgres + the Axum app.
- Source code is bind-mounted into the app container; saving a `.rs` file rebuilds and restarts the service inside the container.
- One worked-end-to-end CRUD example (`items`) so the template is provably wired together, not just empty scaffolding.

This is a template, not a product. Code should be the shortest correct path to a working service, with clear seams for adding features.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Database | PostgreSQL only |
| Rust DB library | `sqlx` 0.8 |
| Dev workflow | Live reload via `cargo-watch` inside the app container |
| Extras included | `tracing` + `tracing-subscriber`, layered config + `.env`, `/health` with DB ping, example CRUD route + migration |
| Migrations | Run automatically on app startup via `sqlx::migrate!("./migrations")` |
| `sqlx` query style | Runtime `sqlx::query_as` / `sqlx::query` — **no** compile-time `query!` macros, so `cargo build` does not require a live DB |

## Stack and crate versions

- **axum 0.8** — uses `tokio::net::TcpListener` + `axum::serve(listener, app)`.
- **tokio 1.x** with `features = ["full"]`.
- **sqlx 0.8** with `runtime-tokio`, `tls-rustls-ring-webpki`, `postgres`, `uuid`, `chrono`, `migrate`. Rustls avoids pulling OpenSSL into the container.
- **tower-http 0.6** for `TraceLayer`.
- **tracing**, **tracing-subscriber** with `env-filter`.
- **serde** + **serde_json** for JSON.
- **figment** (Env + optional Toml providers) for layered config, **dotenvy** to load `.env` in dev.
- **thiserror** for domain errors, **anyhow** at the binary boundary (catch-all in `AppError::Internal`).
- **uuid** with `v7` + `serde` features.
- **chrono** with `serde` for timestamps.

## Project layout

```
backend/
├── Cargo.toml
├── Cargo.lock
├── .env.example                 # committed
├── .env                         # gitignored, dev-only
├── .dockerignore
├── .gitignore
├── compose.yaml
├── Dockerfile                   # dev image with cargo-watch
├── migrations/
│   └── 20260524000001_init_items.sql
├── docs/superpowers/specs/      # this spec lives here
└── src/
    ├── main.rs                  # bootstrap
    ├── config.rs                # AppConfig::from_env()
    ├── state.rs                 # AppState { pool: PgPool }
    ├── error.rs                 # AppError + IntoResponse
    ├── routes/
    │   ├── mod.rs               # builds Router<AppState>
    │   ├── health.rs            # GET /health
    │   └── items.rs             # CRUD handlers
    └── db/
        ├── mod.rs
        └── items.rs             # Item type + query functions
```

**Module responsibilities** (one job per module):

- `config` — owns env parsing and the `AppConfig` struct. No knowledge of HTTP or SQL.
- `state` — defines `AppState` (currently just `PgPool`). The only thing handlers should pull from at the type level.
- `error` — defines `AppError` (an enum of categories: `BadRequest`, `NotFound`, `Conflict`, `Internal`) and its `IntoResponse` impl. Handlers return `Result<T, AppError>`.
- `routes/*` — HTTP shape only: extract, validate, call `db::*`, map errors, return responses. No raw SQL here.
- `db/*` — SQL only. Functions take `&PgPool` (or a transaction) and typed inputs, return typed outputs or `sqlx::Error`. Maps to `AppError` at the route layer.

This separation keeps each file small and lets the user grow the template without each new feature touching three layers at once.

## Endpoints

- `GET /health` → `200 {"status":"ok","db":"ok"}`. Runs `SELECT 1` against the pool with a short timeout. On DB failure: `503 {"status":"degraded","db":"down"}`.
- `GET /items` → list items, ordered by `created_at DESC`. v1 has no pagination — explicitly out of scope.
- `POST /items` `{name: string, description?: string}` → `201` with created `Item`.
- `GET /items/:id` → `200 Item` or `404`.
- `PUT /items/:id` `{name: string, description?: string}` → `200 Item` or `404`. Full replace; `PATCH` is out of scope.
- `DELETE /items/:id` → `204` or `404`.

### `Item` shape

```rust
struct Item {
    id: Uuid,
    name: String,
    description: Option<String>,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}
```

## Initial migration

`migrations/20260524000001_init_items.sql`:

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

`pgcrypto` is the standard way to get `gen_random_uuid()` on stock Postgres images.

## Boot sequence (`main.rs`)

1. Best-effort `dotenvy::dotenv()` (ignore error in container/prod).
2. Init `tracing_subscriber` with `EnvFilter::from_default_env()`; default to `info,backend=debug` if unset.
3. `AppConfig::from_env()` (figment Env provider).
4. Build `PgPool` via `PgPoolOptions::new().max_connections(cfg.db_max_connections).acquire_timeout(...).connect(&cfg.database_url).await?`.
5. `sqlx::migrate!("./migrations").run(&pool).await?` — fail fast on migration error.
6. Build router:
   ```
   Router::new()
       .merge(routes::health::router())
       .nest("/items", routes::items::router())
       .layer(TraceLayer::new_for_http())
       .with_state(AppState { pool })
   ```
7. `axum::serve(TcpListener::bind(("0.0.0.0", cfg.port)).await?, app).await?`.

Migrations running on startup is a deliberate choice for this template: simpler dev loop, one less command. The trade-off (concurrent boots racing on migrations in prod) is acknowledged here so a future production hardening pass can switch to manual `sqlx migrate run` in a deploy step.

## Config (`AppConfig`)

| Field | Env var | Default |
|---|---|---|
| `database_url` | `DATABASE_URL` | required, no default |
| `port` | `APP_PORT` | `3000` |
| `db_max_connections` | `DB_MAX_CONNECTIONS` | `10` |

Missing `DATABASE_URL` fails fast at startup with a clear error.

## Error handling

`AppError` enum, each variant maps to an HTTP status:

| Variant | Status | When |
|---|---|---|
| `NotFound` | 404 | `db::items::get` returns `RowNotFound` |
| `BadRequest(String)` | 400 | Body validation failures |
| `Conflict(String)` | 409 | Reserved for unique-constraint violations (not used in v1 but defined) |
| `Internal(anyhow::Error)` | 500 | `From<sqlx::Error>` catches everything else, logs at `error!` |

Response body: `{"error": "<message>"}`. No stack traces leak to clients.

## Docker Compose

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

**Why the named volumes:** `.:/app` makes the host project tree visible inside the container, but it would also overlay an empty `/app/target` and clobber cargo's registry. Mounting `target-cache` and `cargo-registry` / `cargo-git` on top keeps incremental builds fast across container restarts.

## Dev `Dockerfile`

```dockerfile
FROM rust:1-bookworm

RUN cargo install cargo-watch --locked \
 && cargo install sqlx-cli --no-default-features --features rustls,postgres --locked

WORKDIR /app

EXPOSE 3000

CMD ["cargo", "watch", "-q", "-c", "-w", "src", "-w", "Cargo.toml", "-w", "migrations", "-x", "run"]
```

`sqlx-cli` is included for convenience (creating new migrations from inside the container) even though the app embeds and runs migrations itself.

## Files committed to the repo

- `Cargo.toml`, `Cargo.lock`
- `.env.example` containing the same keys as `compose.yaml` so local-host development is possible without compose
- `.gitignore` (target/, .env, .DS_Store, .idea/ already there)
- `.dockerignore` (target/, .git/, .env, node_modules-style entries)
- `compose.yaml`, `Dockerfile`
- `migrations/20260524000001_init_items.sql`
- All `src/**.rs` files listed in the layout
- This spec under `docs/superpowers/specs/`

## Out of scope (v1)

These are intentionally excluded; they belong to follow-up specs:

- Production multi-stage Dockerfile (distroless / scratch runtime image)
- Authentication / authorization
- Pagination, filtering, sorting
- Rate limiting, CORS configuration beyond defaults
- OpenAPI / generated client
- Integration test harness with a throwaway DB
- CI configuration
- Metrics / Prometheus endpoint
- Manual migration deploy flow

## Acceptance criteria

The template is "done" when, starting from a fresh clone:

1. `docker compose up --build` brings both services up; app logs show migrations applied and `listening on 0.0.0.0:3000`.
2. `curl localhost:3000/health` returns `200 {"status":"ok","db":"ok"}`.
3. The full CRUD cycle works end-to-end:
   - `POST /items` with a valid body returns 201 and an `Item` with a UUID.
   - `GET /items` lists it.
   - `GET /items/:id` returns it.
   - `PUT /items/:id` updates it (and bumps `updated_at`).
   - `DELETE /items/:id` returns 204.
   - `GET /items/:id` then returns 404.
4. Editing `src/routes/items.rs` and saving causes `cargo-watch` inside the container to rebuild and restart; the next request hits the new code.
5. `cargo build` on the host (without Postgres running) succeeds — confirming we have no compile-time DB dependency.
