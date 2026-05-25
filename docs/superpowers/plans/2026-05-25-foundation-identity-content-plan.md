# Foundation, Identity & Content (Phase 0+1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Oecophylla local stack: shared Postgres 18 + Redis 7 + Kafka 4 (KRaft) + Envoy gateway, three Rust Axum services (auth, user, content) on a Cargo workspace with a shared `common` crate, and a SvelteKit (adapter-node, Tailwind) frontend ported from the existing Apple Glass HTML/JSX UI — wired end-to-end so register/login/profile/post creation works against the real backend.

**Architecture:** Microservices behind Envoy on a single docker-compose network. Services share a Postgres DB via shared sqlx migrations. JWT in HttpOnly cookies (`oec_access`, `oec_refresh`). Kafka producers emit `content.created` and `user.followed` events now; consumers belong to Phase 2. Frontend is SSR via `adapter-node`; SvelteKit `hooks.server.ts` proxies `/api/v1/*` to Envoy and handles refresh-on-401. All long-running containers use `debian:trixie-slim` base images.

**Tech Stack:** Rust 1.83 (Axum, SQLx, tokio, rdkafka, deadpool-redis, jsonwebtoken, argon2, tracing), PostgreSQL 18 (`uuidv7()` PK), Redis 7, Apache Kafka 4 KRaft, Envoy v1.32, SvelteKit (adapter-node) + TypeScript + Tailwind CSS, pnpm, vitest, Docker Compose, Debian Trixie base images.

**Companion spec:** `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md` — refer to it for DDL, env keys, endpoint contracts, error envelope, rate-limit table, and decision rationale. The plan duplicates only what an engineer needs to copy-paste.

**Working directory:** Project root is `/Users/nhathaminh/oecophylla`. All paths in this plan are relative to that root unless otherwise noted.

**Git:** The repo root is NOT a git repo (only `backend/.git` exists today). **Task 0** initializes a git repo at the project root and commits the existing files (HTML, scripts/, styles/, tw/, spec, plan) as the baseline. Every subsequent task ends with a commit on this repo.

---

## Milestone overview

| M | Tasks | Outcome |
|---|---|---|
| M0 | 0 | Project-root git repo initialized with current files |
| M1 | 1–3 | Cargo workspace, compose infra (PG/Redis/Kafka/Envoy/Prom/Grafana), migrations job |
| M2 | 4–8 | `crates/common` with config, error, db, redis, kafka, auth, middleware, events/ids/time/models |
| M3 | 9–13 | `auth-service`, `user-service`, `content-service`, Envoy config, end-to-end event smoke |
| M4 | 14–16 | SvelteKit + Tailwind scaffold, `app.css` tokens, lib (api/stores/hooks) |
| M5 | 17–20 | Auth pages, profile + post pages live, feed/admin/mobile pages mock-backed |
| M6 | 21–22 | Seed Phase 1 + README + final manual verify |

---

## Task 0: Initialize project-root git repo

**Files:**
- Create: `.gitignore`
- Create: `.gitattributes`

- [ ] **Step 1: Initialize repo and configure**

```bash
cd /Users/nhathaminh/oecophylla
git init -b main
git config user.name  "$(git -C backend config user.name  || echo 'Oecophylla Dev')"
git config user.email "$(git -C backend config user.email || echo 'dev@example.com')"
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# OS
.DS_Store
*.swp

# IDE
.idea/
.vscode/
*.iml

# Node
node_modules/
.svelte-kit/
build/
dist/
.pnpm-store/

# Rust
target/
**/*.rs.bk
.sqlx/*.json.tmp

# Env
.env
.env.local
.env.*.local

# Docker volumes (compose default named)
data/

# Python
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 3: Write `.gitattributes`**

```gitattributes
* text=auto eol=lf
*.png binary
*.jpg binary
*.ico binary
*.woff2 binary
```

- [ ] **Step 4: Move legacy `backend/` git history into root**

The `backend/` subdirectory is currently its own git repo with only a few commits (Axum scaffold). Phase 0+1 supersedes that scaffold (we are going to rewrite the workspace). Delete the embedded `.git` to avoid a submodule trap, but keep the source files we will reference and overwrite later:

```bash
rm -rf /Users/nhathaminh/oecophylla/backend/.git
```

- [ ] **Step 5: First commit — baseline**

```bash
cd /Users/nhathaminh/oecophylla
git add .gitignore .gitattributes \
        "Oecophylla v2 - Apple Glass.html" \
        "Oecophylla v3 - Tailwind Glass.html" \
        "Oecophylla.html" \
        tweaks-panel.jsx \
        scripts/ styles/ tw/ \
        docs/ \
        CLAUDE.md \
        .remember/ \
        backend/
git commit -m "chore: initialize project-root repo with existing UI + backend scaffold"
```

- [ ] **Step 6: Verify**

Run: `git log --oneline && git status`
Expected: 1 commit, working tree clean.

---

## Task 1: Cargo workspace skeleton

**Files:**
- Create: `backend/Cargo.toml`
- Create: `backend/rust-toolchain.toml`
- Create: `backend/crates/common/Cargo.toml`
- Create: `backend/crates/common/src/lib.rs`
- Create: `backend/services/auth-service/Cargo.toml`
- Create: `backend/services/auth-service/src/main.rs`
- Create: `backend/services/user-service/Cargo.toml`
- Create: `backend/services/user-service/src/main.rs`
- Create: `backend/services/content-service/Cargo.toml`
- Create: `backend/services/content-service/src/main.rs`
- Delete: `backend/src/`, `backend/Cargo.lock`, `backend/target/`, `backend/Dockerfile`, `backend/Makefile`, `backend/compose.yaml`, `backend/migrations/`, `backend/.env.example`, `backend/.dockerignore`, `backend/.gitignore`, `backend/docs/`, `backend/.remember/`, `backend/.claude/`, `backend/.idea/`

- [ ] **Step 1: Wipe the previous single-binary scaffold**

```bash
cd /Users/nhathaminh/oecophylla
rm -rf backend/src backend/target backend/Cargo.lock \
       backend/Dockerfile backend/Makefile backend/compose.yaml \
       backend/migrations backend/docs backend/.remember \
       backend/.claude backend/.idea backend/.env.example \
       backend/.dockerignore backend/.gitignore
rm -f backend/Cargo.toml
```

- [ ] **Step 2: Write `backend/Cargo.toml` (workspace root)**

```toml
[workspace]
resolver = "2"
members = [
    "crates/common",
    "services/auth-service",
    "services/user-service",
    "services/content-service",
]

[workspace.package]
edition = "2021"
rust-version = "1.83"
license = "Apache-2.0"
authors = ["Oecophylla Team"]

[workspace.dependencies]
# Async runtime + HTTP
tokio        = { version = "1.41", features = ["full"] }
axum         = { version = "0.7", features = ["macros", "http2", "tracing"] }
tower        = { version = "0.5", features = ["full"] }
tower-http   = { version = "0.6", features = ["trace", "cors", "request-id", "util", "fs"] }
hyper        = { version = "1", features = ["full"] }
http         = "1"

# Serialization
serde        = { version = "1", features = ["derive"] }
serde_json   = "1"

# DB + cache + queue
sqlx         = { version = "0.8", default-features = false, features = ["runtime-tokio-rustls", "postgres", "uuid", "chrono", "macros", "migrate"] }
deadpool-redis = { version = "0.18", features = ["rt_tokio_1"] }
rdkafka      = { version = "0.36", features = ["cmake-build", "tokio"] }

# Auth + crypto
jsonwebtoken = "9"
argon2       = "0.5"
rand         = "0.8"
sha2         = "0.10"

# Misc
uuid         = { version = "1.11", features = ["v7", "serde"] }
chrono       = { version = "0.4", features = ["serde"] }
thiserror    = "1"
anyhow       = "1"
validator    = { version = "0.19", features = ["derive"] }
config       = { version = "0.14", default-features = false, features = ["toml", "yaml"] }
figment      = { version = "0.10", features = ["env", "toml"] }
metrics      = "0.24"
metrics-exporter-prometheus = "0.16"

# Observability
tracing            = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json", "fmt"] }

# Test
reqwest      = { version = "0.12", default-features = false, features = ["rustls-tls", "json", "cookies"] }

# Local crates
common       = { path = "crates/common" }
```

- [ ] **Step 3: Write `backend/rust-toolchain.toml`**

```toml
[toolchain]
channel = "1.83.0"
components = ["rustfmt", "clippy"]
```

- [ ] **Step 4: Write `backend/crates/common/Cargo.toml`**

```toml
[package]
name = "common"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true

[dependencies]
tokio.workspace = true
axum.workspace = true
tower.workspace = true
tower-http.workspace = true
http.workspace = true
serde.workspace = true
serde_json.workspace = true
sqlx.workspace = true
deadpool-redis.workspace = true
rdkafka.workspace = true
jsonwebtoken.workspace = true
argon2.workspace = true
rand.workspace = true
sha2.workspace = true
uuid.workspace = true
chrono.workspace = true
thiserror.workspace = true
anyhow.workspace = true
validator.workspace = true
figment.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
metrics.workspace = true
metrics-exporter-prometheus.workspace = true
```

- [ ] **Step 5: Stub `backend/crates/common/src/lib.rs`**

```rust
//! Shared infrastructure crate for Oecophylla Rust services.
//!
//! Public modules are filled in across subsequent tasks. This stub exists so
//! the workspace compiles end-to-end from the start.

pub mod config;
pub mod error;
pub mod db;
pub mod redis;
pub mod kafka;
pub mod auth;
pub mod ids;
pub mod time;
pub mod events;
pub mod models;
pub mod middleware;
```

Plus create empty module files so `cargo check` passes:

```bash
mkdir -p backend/crates/common/src/middleware
for f in config error db redis kafka auth ids time events models; do
  echo "// placeholder — filled in later tasks" > backend/crates/common/src/$f.rs
done
cat > backend/crates/common/src/middleware/mod.rs <<'EOF'
pub mod auth;
pub mod rate_limit;
pub mod trace;
EOF
for f in auth rate_limit trace; do
  echo "// placeholder — filled in later tasks" > backend/crates/common/src/middleware/$f.rs
done
```

- [ ] **Step 6: Write three minimal service `Cargo.toml`**

For each of `auth-service`, `user-service`, `content-service`, write `backend/services/<name>/Cargo.toml`:

```toml
[package]
name = "<name>"            # e.g. "auth-service"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true

[dependencies]
common.workspace = true
tokio.workspace = true
axum.workspace = true
tower-http.workspace = true
serde.workspace = true
serde_json.workspace = true
sqlx.workspace = true
deadpool-redis.workspace = true
uuid.workspace = true
chrono.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
anyhow.workspace = true
thiserror.workspace = true

[dev-dependencies]
reqwest.workspace = true
serde_json.workspace = true
tokio.workspace = true
```

- [ ] **Step 7: Stub `backend/services/<name>/src/main.rs` for all three services**

Each writes a one-line health endpoint so the workspace compiles. Use this template, substituting the port:

```rust
use axum::{routing::get, Router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let addr: SocketAddr = "0.0.0.0:8001".parse()?; // auth=8001, user=8002, content=8003
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

For `user-service` use `:8002`, for `content-service` use `:8003`.

- [ ] **Step 8: Verify workspace compiles**

```bash
cd backend && cargo check --workspace
```
Expected: `Finished` with zero errors, possibly some warnings about unused imports in placeholder modules — those are fine for now.

- [ ] **Step 9: Commit**

```bash
cd /Users/nhathaminh/oecophylla
git add backend/
git commit -m "feat(backend): cargo workspace skeleton with common crate + 3 service stubs"
```

---

## Task 2: Docker Compose infra (Postgres, Redis, Kafka, Envoy, Prometheus, Grafana)

**Files:**
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `compose.dev.yaml`
- Create: `envoy/envoy.yaml`
- Create: `infra/prometheus/prometheus.yml`
- Create: `infra/grafana/provisioning/datasources/prometheus.yaml`
- Create: `infra/grafana/provisioning/dashboards/dashboards.yaml`
- Create: `infra/grafana/dashboards/oecophylla-overview.json`
- Create: `infra/kafka/init-topics.sh`

- [ ] **Step 1: `.env.example`** — copy from spec §7.3 verbatim into `/Users/nhathaminh/oecophylla/.env.example`. Then create a working `.env`:

```bash
cd /Users/nhathaminh/oecophylla
cp .env.example .env
```

- [ ] **Step 2: Write `compose.yaml`**

```yaml
name: oecophylla

x-restart: &restart
  restart: unless-stopped

services:
  postgres:
    <<: *restart
    image: postgres:18-trixie
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 10s

  redis:
    <<: *restart
    image: redis:7-trixie
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  kafka:
    <<: *restart
    image: apache/kafka:4.0.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      CLUSTER_ID: ${KAFKA_CLUSTER_ID}
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
    volumes:
      - kafka_data:/var/lib/kafka/data
    healthcheck:
      test: ["CMD", "/opt/kafka/bin/kafka-broker-api-versions.sh", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 30
      start_period: 30s

  init-topics:
    image: apache/kafka:4.0.0
    depends_on:
      kafka:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic oecophylla.content.created --partitions 1 --replication-factor 1 && \
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic oecophylla.user.followed  --partitions 1 --replication-factor 1
    restart: "no"

  migrate:
    image: rust:1.83-trixie
    depends_on:
      postgres:
        condition: service_healthy
    working_dir: /app
    volumes:
      - ./migrations:/app/migrations:ro
    environment:
      DATABASE_URL: ${DATABASE_URL}
    entrypoint: ["/bin/bash", "-c"]
    command:
      - |
        cargo install --quiet sqlx-cli@0.8 --no-default-features --features postgres,rustls && \
        sqlx migrate run --source ./migrations
    restart: "no"

  envoy:
    <<: *restart
    image: envoyproxy/envoy:v1.32-latest
    depends_on:
      auth-service:    { condition: service_started }
      user-service:    { condition: service_started }
      content-service: { condition: service_started }
    volumes:
      - ./envoy/envoy.yaml:/etc/envoy/envoy.yaml:ro
    ports:
      - "8080:8080"
      - "9901:9901"
    command: ["/usr/local/bin/envoy", "-c", "/etc/envoy/envoy.yaml", "--log-level", "info"]

  auth-service:
    <<: *restart
    build:
      context: ./backend
      dockerfile: services/auth-service/Dockerfile
    depends_on:
      postgres:  { condition: service_healthy }
      redis:     { condition: service_healthy }
      kafka:     { condition: service_healthy }
      migrate:   { condition: service_completed_successfully }
    environment: &svc_env
      RUST_LOG: info,sqlx=warn
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      KAFKA_BROKERS: ${KAFKA_BROKERS}
      JWT_SECRET: ${JWT_SECRET}
      JWT_ACCESS_TTL_SECONDS: ${JWT_ACCESS_TTL_SECONDS}
      JWT_REFRESH_TTL_SECONDS: ${JWT_REFRESH_TTL_SECONDS}
      ARGON2_M_COST: ${ARGON2_M_COST}
      ARGON2_T_COST: ${ARGON2_T_COST}
      ARGON2_P_COST: ${ARGON2_P_COST}
      AUTO_PUBLISH: "true"

  user-service:
    <<: *restart
    build:
      context: ./backend
      dockerfile: services/user-service/Dockerfile
    depends_on:
      postgres:  { condition: service_healthy }
      redis:     { condition: service_healthy }
      kafka:     { condition: service_healthy }
      migrate:   { condition: service_completed_successfully }
    environment:
      <<: *svc_env

  content-service:
    <<: *restart
    build:
      context: ./backend
      dockerfile: services/content-service/Dockerfile
    depends_on:
      postgres:  { condition: service_healthy }
      redis:     { condition: service_healthy }
      kafka:     { condition: service_healthy }
      migrate:   { condition: service_completed_successfully }
    environment:
      <<: *svc_env

  frontend:
    <<: *restart
    build:
      context: ./frontend
    depends_on:
      envoy: { condition: service_started }
    environment:
      ORIGIN: ${ORIGIN}
      ENVOY_URL: ${ENVOY_URL}
      PUBLIC_API_BASE: ${PUBLIC_API_BASE}
    ports:
      - "3000:3000"

  prometheus:
    <<: *restart
    image: prom/prometheus:v3.0.0
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    <<: *restart
    image: grafana/grafana:11.4.0
    depends_on: [prometheus]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GF_SECURITY_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3001:3000"

volumes:
  postgres_data:
  redis_data:
  kafka_data:
```

- [ ] **Step 3: Write `compose.dev.yaml` (override: expose backend ports, mount source for hot dev)**

```yaml
services:
  postgres: { ports: ["5432:5432"] }
  redis:    { ports: ["6379:6379"] }
  kafka:    { ports: ["9092:9092"] }
  auth-service:    { ports: ["8001:8001"] }
  user-service:    { ports: ["8002:8002"] }
  content-service: { ports: ["8003:8003"] }
```

- [ ] **Step 4: Write `envoy/envoy.yaml`**

```yaml
admin:
  address:
    socket_address: { address: 0.0.0.0, port_value: 9901 }

static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address: { address: 0.0.0.0, port_value: 8080 }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                codec_type: AUTO
                route_config:
                  name: local
                  virtual_hosts:
                    - name: oecophylla
                      domains: ["*"]
                      cors:
                        allow_origin_string_match:
                          - prefix: "http://localhost:3000"
                        allow_methods: "GET, POST, PUT, DELETE, OPTIONS"
                        allow_headers: "content-type, authorization, cookie, x-request-id, x-requested-with"
                        allow_credentials: true
                        max_age: "1728000"
                      routes:
                        - match: { prefix: "/api/v1/auth/" }
                          route:  { cluster: auth_cluster, prefix_rewrite: "/api/v1/auth/" }
                        - match: { prefix: "/api/v1/users/" }
                          route:  { cluster: user_cluster, prefix_rewrite: "/api/v1/users/" }
                        - match: { prefix: "/api/v1/users" }
                          route:  { cluster: user_cluster }
                        - match: { prefix: "/api/v1/posts/" }
                          route:  { cluster: content_cluster, prefix_rewrite: "/api/v1/posts/" }
                        - match: { prefix: "/api/v1/posts" }
                          route:  { cluster: content_cluster }
                http_filters:
                  - name: envoy.filters.http.cors
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.cors.v3.Cors
                  - name: envoy.filters.http.local_ratelimit
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                      stat_prefix: ingress_http_rl
                      token_bucket:
                        max_tokens: 60
                        tokens_per_fill: 60
                        fill_interval: 60s
                      filter_enabled:
                        runtime_key: local_rate_limit_enabled
                        default_value: { numerator: 100, denominator: HUNDRED }
                      filter_enforced:
                        runtime_key: local_rate_limit_enforced
                        default_value: { numerator: 100, denominator: HUNDRED }
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
    - name: auth_cluster
      type: STRICT_DNS
      connect_timeout: 1s
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: auth_cluster
        endpoints:
          - lb_endpoints:
              - endpoint: { address: { socket_address: { address: auth-service, port_value: 8001 } } }
      health_checks:
        - timeout: 1s
          interval: 5s
          unhealthy_threshold: 3
          healthy_threshold: 1
          http_health_check: { path: "/health" }
    - name: user_cluster
      type: STRICT_DNS
      connect_timeout: 1s
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: user_cluster
        endpoints:
          - lb_endpoints:
              - endpoint: { address: { socket_address: { address: user-service, port_value: 8002 } } }
      health_checks:
        - timeout: 1s
          interval: 5s
          unhealthy_threshold: 3
          healthy_threshold: 1
          http_health_check: { path: "/health" }
    - name: content_cluster
      type: STRICT_DNS
      connect_timeout: 1s
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: content_cluster
        endpoints:
          - lb_endpoints:
              - endpoint: { address: { socket_address: { address: content-service, port_value: 8003 } } }
      health_checks:
        - timeout: 1s
          interval: 5s
          unhealthy_threshold: 3
          healthy_threshold: 1
          http_health_check: { path: "/health" }
```

- [ ] **Step 5: Write `infra/prometheus/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: oecophylla-services
    static_configs:
      - targets:
          - "auth-service:8001"
          - "user-service:8002"
          - "content-service:8003"
        labels: { stack: oecophylla }
  - job_name: envoy
    metrics_path: /stats/prometheus
    static_configs:
      - targets: ["envoy:9901"]
```

- [ ] **Step 6: Grafana provisioning files**

`infra/grafana/provisioning/datasources/prometheus.yaml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

`infra/grafana/provisioning/dashboards/dashboards.yaml`:
```yaml
apiVersion: 1
providers:
  - name: default
    folder: ''
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

`infra/grafana/dashboards/oecophylla-overview.json` — minimal placeholder dashboard:
```json
{
  "title": "Oecophylla Overview",
  "panels": [
    { "id": 1, "type": "stat", "title": "Services up",
      "targets": [{ "expr": "sum(up{job=\"oecophylla-services\"})" }] }
  ],
  "schemaVersion": 39, "version": 1, "tags": ["oecophylla"]
}
```

- [ ] **Step 7: `infra/kafka/init-topics.sh`** (currently the inline `command:` in compose does this; the standalone script is kept for manual rerun)

```bash
#!/usr/bin/env bash
set -euo pipefail
BOOTSTRAP="${KAFKA_BROKERS:-kafka:9092}"
for topic in oecophylla.content.created oecophylla.user.followed; do
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic "$topic" --partitions 1 --replication-factor 1
done
```
Make it executable: `chmod +x infra/kafka/init-topics.sh`.

- [ ] **Step 8: Boot infra-only smoke test**

```bash
cd /Users/nhathaminh/oecophylla
docker compose up -d postgres redis kafka
```

Wait ≤ 60s, then:
```bash
docker compose ps
docker compose exec postgres psql -U oecophylla -d oecophylla -c "SELECT uuidv7();"
docker compose exec redis redis-cli -a redissecret ping
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```
Expected: postgres returns a UUID; redis returns `PONG`; kafka returns empty list (topics not yet created — that's Task 3's job after migrations).

- [ ] **Step 9: Commit**

```bash
git add .env.example compose.yaml compose.dev.yaml envoy/ infra/
git commit -m "feat(infra): compose stack — pg18, redis7, kafka4 kraft, envoy, prom, grafana"
```

---

## Task 3: Migrations + migrate job

**Files:**
- Create: `migrations/20260525000001_init_enums.sql`
- Create: `migrations/20260525000002_users.sql`
- Create: `migrations/20260525000003_follows.sql`
- Create: `migrations/20260525000004_posts.sql`

- [ ] **Step 1: Copy migration contents from spec §4.1–4.4 verbatim into each of the 4 files.**

For exact contents, see `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md` sections 4.2, 4.3, 4.4. Migration 4.1 (enums) goes into the first file.

- [ ] **Step 2: Run migrate job via compose**

```bash
docker compose up migrate
```
Expected output: `Applied 20260525000001/migrate init_enums (...)`, repeat for the other three. Exit code 0.

- [ ] **Step 3: Verify schema**

```bash
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\dt+ public.*"
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d users"
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d posts"
```
Expected: three tables (`users`, `follows`, `posts`), `id` defaults `uuidv7()`, all indexes from §4 present.

- [ ] **Step 4: Verify init-topics**

```bash
docker compose up init-topics
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```
Expected: `oecophylla.content.created` and `oecophylla.user.followed`.

- [ ] **Step 5: Commit**

```bash
git add migrations/
git commit -m "feat(db): initial migrations — enums, users, follows, posts (uuidv7 PKs)"
```

---

## Task 4: Common — error + config

**Files:**
- Modify: `backend/crates/common/src/error.rs`
- Modify: `backend/crates/common/src/config.rs`

- [ ] **Step 1: Implement `error.rs`**

```rust
use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("validation failed: {field}: {message}")]
    Validation { field: String, message: String },
    #[error("unauthorized")]
    Unauthorized,
    #[error("forbidden")]
    Forbidden,
    #[error("not found: {kind}")]
    NotFound { kind: String },
    #[error("conflict: {kind}")]
    Conflict { kind: String },
    #[error("rate limited (retry in {retry_after_s}s)")]
    RateLimited { retry_after_s: u64 },
    #[error(transparent)]
    Db(#[from] sqlx::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

#[derive(Serialize)]
struct ErrEnvelope<'a> {
    error: ErrBody<'a>,
}
#[derive(Serialize)]
struct ErrBody<'a> {
    code: &'a str,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    details: Option<serde_json::Value>,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, message, details) = match &self {
            AppError::Validation { field, message } => (
                StatusCode::BAD_REQUEST,
                "VALIDATION_FAILED",
                message.clone(),
                Some(serde_json::json!({ "field": field })),
            ),
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, "UNAUTHORIZED", self.to_string(), None),
            AppError::Forbidden    => (StatusCode::FORBIDDEN,    "FORBIDDEN",    self.to_string(), None),
            AppError::NotFound { kind } => (StatusCode::NOT_FOUND, "NOT_FOUND", format!("{kind} not found"), None),
            AppError::Conflict { kind } => (StatusCode::CONFLICT,  "CONFLICT",  format!("{kind} already exists"), None),
            AppError::RateLimited { retry_after_s } => {
                let mut resp = (
                    StatusCode::TOO_MANY_REQUESTS,
                    Json(ErrEnvelope { error: ErrBody { code: "RATE_LIMITED", message: self.to_string(), details: None }})
                ).into_response();
                resp.headers_mut().insert("Retry-After", retry_after_s.to_string().parse().unwrap());
                return resp;
            }
            AppError::Db(e) => {
                tracing::error!(error = ?e, "db error");
                (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "internal error".into(), None)
            }
            AppError::Other(e) => {
                tracing::error!(error = ?e, "internal error");
                (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "internal error".into(), None)
            }
        };
        (status, Json(ErrEnvelope { error: ErrBody { code, message, details }})).into_response()
    }
}

pub type AppResult<T> = std::result::Result<T, AppError>;
```

- [ ] **Step 2: Implement `config.rs`**

```rust
use figment::{providers::Env, Figment};
use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct SharedConfig {
    pub database_url: String,
    pub redis_url: String,
    pub kafka_brokers: String,
    pub jwt_secret: String,
    pub jwt_access_ttl_seconds: i64,
    pub jwt_refresh_ttl_seconds: i64,
    #[serde(default = "default_m_cost")] pub argon2_m_cost: u32,
    #[serde(default = "default_t_cost")] pub argon2_t_cost: u32,
    #[serde(default = "default_p_cost")] pub argon2_p_cost: u32,
    #[serde(default)] pub auto_publish: bool,
    #[serde(default = "default_bind")] pub bind: String,
}

fn default_m_cost() -> u32 { 19456 }
fn default_t_cost() -> u32 { 2 }
fn default_p_cost() -> u32 { 1 }
fn default_bind() -> String { "0.0.0.0:8001".into() }

impl SharedConfig {
    pub fn from_env() -> anyhow::Result<Self> {
        let c: SharedConfig = Figment::new()
            .merge(Env::raw().lowercase(true))
            .extract()?;
        Ok(c)
    }
}
```

- [ ] **Step 3: Verify**

```bash
cd backend && cargo check --workspace
```
Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add backend/crates/common/src/{error.rs,config.rs}
git commit -m "feat(common): error envelope + config loader"
```

---

## Task 5: Common — db, redis, kafka, ids, time

**Files:**
- Modify: `backend/crates/common/src/db.rs`
- Modify: `backend/crates/common/src/redis.rs`
- Modify: `backend/crates/common/src/kafka.rs`
- Modify: `backend/crates/common/src/ids.rs`
- Modify: `backend/crates/common/src/time.rs`

- [ ] **Step 1: `db.rs`**

```rust
use sqlx::{postgres::PgPoolOptions, PgPool};
use std::time::Duration;

pub async fn pg_pool(url: &str, max_conn: u32) -> anyhow::Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_conn)
        .acquire_timeout(Duration::from_secs(5))
        .connect(url)
        .await?;
    Ok(pool)
}
```

- [ ] **Step 2: `redis.rs`**

```rust
use deadpool_redis::{Config, Runtime, Pool};

pub fn redis_pool(url: &str) -> anyhow::Result<Pool> {
    let cfg = Config::from_url(url);
    Ok(cfg.create_pool(Some(Runtime::Tokio1))?)
}
```

- [ ] **Step 3: `kafka.rs`**

```rust
use rdkafka::{producer::{FutureProducer, FutureRecord}, ClientConfig};
use serde::Serialize;
use std::time::Duration;

#[derive(Clone)]
pub struct Producer { inner: FutureProducer }

impl Producer {
    pub fn new(brokers: &str) -> anyhow::Result<Self> {
        let inner: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", brokers)
            .set("enable.idempotence", "true")
            .set("acks", "all")
            .set("compression.type", "lz4")
            .set("message.timeout.ms", "10000")
            .create()?;
        Ok(Self { inner })
    }

    pub async fn produce_json<T: Serialize>(&self, topic: &str, key: &str, payload: &T) {
        let body = match serde_json::to_vec(payload) {
            Ok(b) => b,
            Err(e) => { tracing::error!(error=?e, topic, "serialize event"); return; }
        };
        let rec = FutureRecord::to(topic).key(key).payload(&body);
        if let Err((e, _)) = self.inner.send(rec, Duration::from_secs(5)).await {
            tracing::error!(error=?e, topic, key, "kafka produce failed");
        }
    }
}
```

- [ ] **Step 4: `ids.rs`**

```rust
use uuid::Uuid;
pub fn new_id() -> Uuid { Uuid::now_v7() }
```

- [ ] **Step 5: `time.rs`**

```rust
use chrono::{DateTime, Utc};
pub fn now() -> DateTime<Utc> { Utc::now() }
```

- [ ] **Step 6: Verify + commit**

```bash
cd backend && cargo check --workspace
git add backend/crates/common/src/{db.rs,redis.rs,kafka.rs,ids.rs,time.rs}
git commit -m "feat(common): pg pool, redis pool, kafka producer wrapper, id/time helpers"
```

---

## Task 6: Common — auth (JWT, cookies, argon2)

**Files:**
- Modify: `backend/crates/common/src/auth.rs`
- Modify: `backend/crates/common/src/models.rs`

- [ ] **Step 1: Implement `models.rs`**

```rust
use serde::{Deserialize, Serialize};
use sqlx::Type;
use uuid::Uuid;

#[derive(Debug, Copy, Clone, PartialEq, Eq, Type, Serialize, Deserialize)]
#[sqlx(type_name = "user_role", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum UserRole { User, Creator, Admin }

#[derive(Debug, Copy, Clone, PartialEq, Eq, Type, Serialize, Deserialize)]
#[sqlx(type_name = "post_status", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum PostStatus { Pending, Published, Hidden, Flagged }

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct AuthUser { pub id: Uuid, pub role: UserRole }
```

- [ ] **Step 2: Implement `auth.rs`**

```rust
use argon2::{Argon2, PasswordHasher, PasswordVerifier, password_hash::{SaltString, PasswordHash, rand_core::OsRng}};
use axum::http::HeaderValue;
use chrono::{Utc, Duration};
use jsonwebtoken::{encode, decode, EncodingKey, DecodingKey, Header, Validation, Algorithm};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::models::UserRole;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: Uuid,
    pub role: UserRole,
    pub exp: i64,
    pub iat: i64,
    pub jti: Uuid,
}

pub fn issue_access(secret: &[u8], ttl_seconds: i64, sub: Uuid, role: UserRole) -> anyhow::Result<String> {
    let now = Utc::now();
    let claims = Claims {
        sub, role,
        exp: (now + Duration::seconds(ttl_seconds)).timestamp(),
        iat: now.timestamp(),
        jti: Uuid::now_v7(),
    };
    Ok(encode(&Header::new(Algorithm::HS256), &claims, &EncodingKey::from_secret(secret))?)
}

pub fn verify_access(secret: &[u8], token: &str) -> anyhow::Result<Claims> {
    let v = Validation::new(Algorithm::HS256);
    let data = decode::<Claims>(token, &DecodingKey::from_secret(secret), &v)?;
    Ok(data.claims)
}

/// Opaque 32-byte refresh token, base64url-encoded for cookie transport.
pub fn new_refresh_token() -> (String, String) {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    use base64::Engine;
    let token = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes);
    let hash  = sha256_hex(&token);
    (token, hash)
}

pub fn sha256_hex(s: &str) -> String {
    let mut h = Sha256::new();
    h.update(s.as_bytes());
    hex::encode(h.finalize())
}

pub fn hash_password(plain: &str, m_cost: u32, t_cost: u32, p_cost: u32) -> anyhow::Result<String> {
    let salt = SaltString::generate(&mut OsRng);
    let params = argon2::Params::new(m_cost, t_cost, p_cost, None)
        .map_err(|e| anyhow::anyhow!("argon2 params: {e}"))?;
    let argon = Argon2::new(argon2::Algorithm::Argon2id, argon2::Version::V0x13, params);
    Ok(argon.hash_password(plain.as_bytes(), &salt)
        .map_err(|e| anyhow::anyhow!("argon2 hash: {e}"))?
        .to_string())
}

pub fn verify_password(plain: &str, hash: &str) -> bool {
    let Ok(parsed) = PasswordHash::new(hash) else { return false; };
    Argon2::default().verify_password(plain.as_bytes(), &parsed).is_ok()
}

pub struct CookieOpts {
    pub name: &'static str,
    pub value: String,
    pub path: &'static str,
    pub max_age_seconds: i64,
    pub same_site: &'static str, // "Lax" | "Strict"
    pub secure: bool,
}
pub fn cookie_header(opts: CookieOpts) -> HeaderValue {
    let secure = if opts.secure { "; Secure" } else { "" };
    let v = format!(
        "{}={}; Path={}; Max-Age={}; HttpOnly; SameSite={}{}",
        opts.name, opts.value, opts.path, opts.max_age_seconds, opts.same_site, secure
    );
    HeaderValue::from_str(&v).expect("valid cookie header")
}
pub fn clear_cookie_header(name: &'static str, path: &'static str) -> HeaderValue {
    let v = format!("{}=; Path={}; Max-Age=0; HttpOnly", name, path);
    HeaderValue::from_str(&v).unwrap()
}
```

- [ ] **Step 3: Add missing deps to `common/Cargo.toml`**

```toml
base64 = "0.22"
hex    = "0.4"
```

(Also add `base64 = "0.22"` and `hex = "0.4"` to the workspace `Cargo.toml`'s `[workspace.dependencies]` and reference them with `.workspace = true` if you prefer.)

- [ ] **Step 4: Verify + commit**

```bash
cd backend && cargo check --workspace
git add backend/crates/common/{Cargo.toml,src/auth.rs,src/models.rs}
git commit -m "feat(common): jwt, argon2, cookie helpers, shared role/status enums"
```

---

## Task 7: Common — middleware (auth, rate_limit, trace) + events

**Files:**
- Modify: `backend/crates/common/src/middleware/auth.rs`
- Modify: `backend/crates/common/src/middleware/rate_limit.rs`
- Modify: `backend/crates/common/src/middleware/trace.rs`
- Modify: `backend/crates/common/src/events.rs`

- [ ] **Step 1: `middleware/auth.rs`**

```rust
use axum::{extract::{Request, State}, http::{header::COOKIE, StatusCode}, middleware::Next, response::Response};
use std::sync::Arc;

use crate::{auth::verify_access, error::AppError, models::AuthUser};

#[derive(Clone)]
pub struct AuthState { pub jwt_secret: Arc<Vec<u8>> }

pub async fn require_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let token = extract_access_cookie(&req).ok_or(AppError::Unauthorized)?;
    let claims = verify_access(&state.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
    req.extensions_mut().insert(AuthUser { id: claims.sub, role: claims.role });
    Ok(next.run(req).await)
}

pub async fn optional_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Response {
    if let Some(token) = extract_access_cookie(&req) {
        if let Ok(claims) = verify_access(&state.jwt_secret, &token) {
            req.extensions_mut().insert(AuthUser { id: claims.sub, role: claims.role });
        }
    }
    next.run(req).await
}

fn extract_access_cookie(req: &Request) -> Option<String> {
    let raw = req.headers().get(COOKIE)?.to_str().ok()?;
    for kv in raw.split(';') {
        let kv = kv.trim();
        if let Some(rest) = kv.strip_prefix("oec_access=") {
            return Some(rest.to_string());
        }
    }
    None
}
```

- [ ] **Step 2: `middleware/rate_limit.rs`**

```rust
use axum::{extract::{Request, State}, http::StatusCode, middleware::Next, response::Response};
use deadpool_redis::Pool;
use redis::AsyncCommands;
use std::sync::Arc;

use crate::error::AppError;

#[derive(Clone)]
pub struct RateLimitState {
    pub redis: Pool,
    pub limit_public: u32,
    pub limit_authed: u32,
}

pub async fn ip_rate_limit(
    State(state): State<RateLimitState>,
    req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let ip = req.headers().get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or("").trim().to_string())
        .unwrap_or_else(|| "unknown".into());
    let minute = chrono::Utc::now().timestamp() / 60;
    let key = format!("rate:ip:{ip}:{minute}");
    let mut conn = state.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let n: i64 = conn.incr(&key, 1).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    if n == 1 {
        let _: () = conn.expire(&key, 65).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    }
    if (n as u32) > state.limit_public {
        return Err(AppError::RateLimited { retry_after_s: 60 });
    }
    Ok(next.run(req).await)
}
```

Add `redis = "0.27"` to common's `Cargo.toml` (deadpool-redis re-exports an old version; pulling the up-to-date crate directly gives us `AsyncCommands`).

- [ ] **Step 3: `middleware/trace.rs`**

```rust
use tracing_subscriber::{EnvFilter, fmt, prelude::*};

pub fn init_tracing(service: &str) {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer().json().with_target(false).with_current_span(false))
        .init();
    tracing::info!(service, "tracing initialized");
}
```

- [ ] **Step 4: `events.rs`**

```rust
use chrono::{DateTime, Utc};
use serde::Serialize;
use uuid::Uuid;

use crate::ids::new_id;

#[derive(Serialize)]
pub struct Envelope<T: Serialize> {
    pub event_id: Uuid,
    pub event_type: &'static str,
    pub event_version: u8,
    pub occurred_at: DateTime<Utc>,
    pub producer: &'static str,
    pub data: T,
}

impl<T: Serialize> Envelope<T> {
    pub fn new(event_type: &'static str, producer: &'static str, data: T) -> Self {
        Self { event_id: new_id(), event_type, event_version: 1, occurred_at: Utc::now(), producer, data }
    }
}

#[derive(Serialize)]
pub struct ContentCreated {
    pub post_id: Uuid,
    pub author_id: Uuid,
    pub content: String,
    pub tags: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Serialize)]
pub struct UserFollowed {
    pub follower_id: Uuid,
    pub followee_id: Uuid,
    pub followed_at: DateTime<Utc>,
}

pub const TOPIC_CONTENT_CREATED: &str = "oecophylla.content.created";
pub const TOPIC_USER_FOLLOWED:  &str = "oecophylla.user.followed";
```

- [ ] **Step 5: Verify + commit**

```bash
cd backend && cargo check --workspace
git add backend/crates/common/
git commit -m "feat(common): auth+ratelimit+trace middleware, kafka event payloads"
```

---

## Task 8: auth-service — full implementation + smoke test

**Files:**
- Modify: `backend/services/auth-service/src/main.rs`
- Create: `backend/services/auth-service/src/state.rs`
- Create: `backend/services/auth-service/src/handlers.rs`
- Create: `backend/services/auth-service/src/repo.rs`
- Create: `backend/services/auth-service/tests/smoke.rs`
- Create: `backend/services/auth-service/Dockerfile`

- [ ] **Step 1: Write the failing smoke test first (`tests/smoke.rs`)**

```rust
//! Smoke tests assume auth-service is running on http://127.0.0.1:8001 against
//! the same Postgres/Redis from compose.dev.yaml. Run with:
//!   docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka
//!   cargo run -p auth-service &
//!   cargo test -p auth-service --test smoke -- --test-threads=1

use reqwest::{Client, StatusCode};
use serde_json::json;

fn client() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}
const BASE: &str = "http://127.0.0.1:8001";

#[tokio::test]
async fn register_login_refresh_logout() {
    let c = client();
    let uniq = uuid::Uuid::now_v7().simple().to_string();
    let username = format!("u{}", &uniq[..10]);
    let email = format!("{username}@example.com");

    // Register
    let r = c.post(format!("{BASE}/api/v1/auth/register"))
        .json(&json!({ "username": username, "email": email, "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let user: serde_json::Value = r.json().await.unwrap();
    assert!(user["user"]["id"].as_str().unwrap().len() == 36);

    // Duplicate
    let r = c.post(format!("{BASE}/api/v1/auth/register"))
        .json(&json!({ "username": username, "email": email, "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CONFLICT);

    // Wrong password → 401, no leak
    let r = c.post(format!("{BASE}/api/v1/auth/login"))
        .json(&json!({ "email_or_username": email, "password": "wrong" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);

    // Refresh rotates
    let r = c.post(format!("{BASE}/api/v1/auth/refresh")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);

    // Logout invalidates refresh
    let r = c.delete(format!("{BASE}/api/v1/auth/logout")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::NO_CONTENT);
    let r = c.post(format!("{BASE}/api/v1/auth/refresh")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);
}
```

- [ ] **Step 2: Implement `state.rs`**

```rust
use common::config::SharedConfig;
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;
use std::sync::Arc;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub cfg: Arc<SharedConfig>,
}
```

- [ ] **Step 3: Implement `repo.rs`** — users table access

```rust
use common::{error::AppError, models::UserRole};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, Clone)]
pub struct UserRow {
    pub id: Uuid,
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub role: UserRole,
    pub display_name: Option<String>,
    pub avatar_url: Option<String>,
}

pub async fn insert_user(
    db: &PgPool,
    username: &str, email: &str, password_hash: &str, display_name: Option<&str>,
) -> Result<UserRow, AppError> {
    sqlx::query_as::<_, UserRow>(
        "INSERT INTO users (username, email, password_hash, display_name)
         VALUES ($1, $2, $3, $4)
         RETURNING id, username, email, password_hash, role, display_name, avatar_url"
    )
    .bind(username).bind(email).bind(password_hash).bind(display_name)
    .fetch_one(db).await
    .map_err(|e| match e {
        sqlx::Error::Database(d) if d.code().as_deref() == Some("23505") =>
            AppError::Conflict { kind: "user".into() },
        other => AppError::Db(other),
    })
}

pub async fn find_by_email_or_username(db: &PgPool, key: &str) -> Result<Option<UserRow>, AppError> {
    Ok(sqlx::query_as::<_, UserRow>(
        "SELECT id, username, email, password_hash, role, display_name, avatar_url
         FROM users WHERE email = $1 OR username = $1"
    )
    .bind(key).fetch_optional(db).await?)
}

pub async fn find_by_id(db: &PgPool, id: Uuid) -> Result<Option<UserRow>, AppError> {
    Ok(sqlx::query_as::<_, UserRow>(
        "SELECT id, username, email, password_hash, role, display_name, avatar_url
         FROM users WHERE id = $1"
    )
    .bind(id).fetch_optional(db).await?)
}
```

- [ ] **Step 4: Implement `handlers.rs`** — full endpoint set

```rust
use axum::{extract::State, http::{header::{HeaderMap, SET_COOKIE}, StatusCode}, response::{IntoResponse, Response}, Json};
use common::{auth::*, error::{AppError, AppResult}, models::UserRole};
use deadpool_redis::redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use validator::Validate;

use crate::{state::AppState, repo};

#[derive(Deserialize, Validate)]
pub struct RegisterReq {
    #[validate(regex(path = "USERNAME_RE", message = "username must be 3-30 chars, a-z0-9_"))]
    pub username: String,
    #[validate(email)]
    pub email: String,
    #[validate(length(min = 8, max = 128))]
    pub password: String,
    pub display_name: Option<String>,
}

static USERNAME_RE: once_cell::sync::Lazy<regex::Regex> =
    once_cell::sync::Lazy::new(|| regex::Regex::new(r"^[a-z0-9_]{3,30}$").unwrap());

#[derive(Deserialize)]
pub struct LoginReq { pub email_or_username: String, pub password: String }

#[derive(Serialize)]
pub struct UserDto { pub id: Uuid, pub username: String, pub email: String, pub role: UserRole, pub display_name: Option<String>, pub avatar_url: Option<String> }
#[derive(Serialize)]
pub struct AuthBody { pub user: UserDto }

fn dto(u: repo::UserRow) -> UserDto {
    UserDto { id: u.id, username: u.username, email: u.email, role: u.role, display_name: u.display_name, avatar_url: u.avatar_url }
}

pub async fn register(State(s): State<AppState>, Json(body): Json<RegisterReq>) -> AppResult<Response> {
    body.validate().map_err(|e| AppError::Validation { field: "body".into(), message: e.to_string() })?;
    let hash = hash_password(&body.password, s.cfg.argon2_m_cost, s.cfg.argon2_t_cost, s.cfg.argon2_p_cost)
        .map_err(AppError::Other)?;
    let user = repo::insert_user(&s.db, &body.username, &body.email, &hash, body.display_name.as_deref()).await?;
    let response = build_auth_response(&s, &user).await?;
    Ok(response)
}

pub async fn login(State(s): State<AppState>, Json(body): Json<LoginReq>) -> AppResult<Response> {
    let user = repo::find_by_email_or_username(&s.db, &body.email_or_username).await?
        .ok_or(AppError::Unauthorized)?;
    if !verify_password(&body.password, &user.password_hash) {
        return Err(AppError::Unauthorized);
    }
    build_auth_response(&s, &user).await
}

pub async fn refresh(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    let token = extract_cookie(&headers, "oec_refresh").ok_or(AppError::Unauthorized)?;
    let hash = sha256_hex(&token);
    let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let key = format!("session:refresh:{hash}");
    let user_id: Option<String> = conn.get(&key).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let user_id: Uuid = user_id.ok_or(AppError::Unauthorized)?.parse().map_err(|_| AppError::Unauthorized)?;
    let _: () = conn.del(&key).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let user = repo::find_by_id(&s.db, user_id).await?.ok_or(AppError::Unauthorized)?;
    build_auth_response(&s, &user).await
}

pub async fn logout(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    if let Some(token) = extract_cookie(&headers, "oec_refresh") {
        let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
        let _: i64 = conn.del(format!("session:refresh:{}", sha256_hex(&token))).await
            .map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    }
    let mut resp = StatusCode::NO_CONTENT.into_response();
    resp.headers_mut().append(SET_COOKIE, clear_cookie_header("oec_access", "/"));
    resp.headers_mut().append(SET_COOKIE, clear_cookie_header("oec_refresh", "/api/v1/auth"));
    Ok(resp)
}

pub async fn me(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Json<AuthBody>> {
    let token = extract_cookie(&headers, "oec_access").ok_or(AppError::Unauthorized)?;
    let claims = verify_access(s.cfg.jwt_secret.as_bytes(), &token).map_err(|_| AppError::Unauthorized)?;
    let user = repo::find_by_id(&s.db, claims.sub).await?.ok_or(AppError::Unauthorized)?;
    Ok(Json(AuthBody { user: dto(user) }))
}

async fn build_auth_response(s: &AppState, user: &repo::UserRow) -> AppResult<Response> {
    let access = issue_access(s.cfg.jwt_secret.as_bytes(), s.cfg.jwt_access_ttl_seconds, user.id, user.role)
        .map_err(AppError::Other)?;
    let (refresh_token, refresh_hash) = new_refresh_token();
    let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let _: () = conn.set_ex(format!("session:refresh:{refresh_hash}"), user.id.to_string(), s.cfg.jwt_refresh_ttl_seconds as u64)
        .await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;

    let body = Json(AuthBody { user: dto(user.clone()) }).into_response();
    let (mut parts, body) = body.into_parts();
    parts.headers.append(SET_COOKIE, cookie_header(CookieOpts {
        name: "oec_access", value: access, path: "/", max_age_seconds: s.cfg.jwt_access_ttl_seconds, same_site: "Lax", secure: false }));
    parts.headers.append(SET_COOKIE, cookie_header(CookieOpts {
        name: "oec_refresh", value: refresh_token, path: "/api/v1/auth", max_age_seconds: s.cfg.jwt_refresh_ttl_seconds, same_site: "Strict", secure: false }));
    Ok(Response::from_parts(parts, body))
}

fn extract_cookie(h: &HeaderMap, name: &str) -> Option<String> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    raw.split(';').find_map(|kv| {
        let kv = kv.trim();
        kv.strip_prefix(&format!("{name}="))
    }).map(String::from)
}
```

Add `validator`, `regex`, `once_cell` to `auth-service/Cargo.toml`:
```toml
validator  = { workspace = true }
regex      = "1"
once_cell  = "1"
```

- [ ] **Step 5: Wire `main.rs`**

```rust
use axum::{Router, routing::{post, delete, get}};
use common::{config::SharedConfig, db::pg_pool, redis::redis_pool, middleware::trace::init_tracing};
use std::{net::SocketAddr, sync::Arc};

mod state; mod handlers; mod repo;
use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("auth-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("AUTH_BIND").unwrap_or_else(|_| "0.0.0.0:8001".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let state = AppState { db, redis, cfg: Arc::new(cfg.clone()) };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/api/v1/auth/register", post(handlers::register))
        .route("/api/v1/auth/login",    post(handlers::login))
        .route("/api/v1/auth/refresh",  post(handlers::refresh))
        .route("/api/v1/auth/logout",   delete(handlers::logout))
        .route("/api/v1/auth/me",       get(handlers::me))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "auth-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

- [ ] **Step 6: Write `Dockerfile`** at `backend/services/auth-service/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7
FROM rust:1.83-trixie AS builder
WORKDIR /app
COPY . .
RUN cargo build --release -p auth-service

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/auth-service /usr/local/bin/auth-service
EXPOSE 8001
ENTRYPOINT ["/usr/local/bin/auth-service"]
```

- [ ] **Step 7: Run service + smoke**

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate
cd backend
DATABASE_URL=postgres://oecophylla:secret@127.0.0.1:5432/oecophylla \
REDIS_URL=redis://:redissecret@127.0.0.1:6379 \
KAFKA_BROKERS=127.0.0.1:9092 \
JWT_SECRET=please-change-this-32-or-more-chars \
JWT_ACCESS_TTL_SECONDS=900 JWT_REFRESH_TTL_SECONDS=604800 \
ARGON2_M_COST=4096 ARGON2_T_COST=1 ARGON2_P_COST=1 \
cargo run -p auth-service &
sleep 3
cargo test -p auth-service --test smoke -- --test-threads=1
kill %1
```
Expected: smoke test passes.

- [ ] **Step 8: Commit**

```bash
git add backend/services/auth-service/
git commit -m "feat(auth-service): register/login/refresh/logout/me with argon2 + httponly cookies"
```

---

## Task 9: user-service — profile, follow, search

**Files:**
- Modify: `backend/services/user-service/src/main.rs`
- Create: `backend/services/user-service/src/{state,handlers,repo}.rs`
- Create: `backend/services/user-service/tests/smoke.rs`
- Create: `backend/services/user-service/Dockerfile`

- [ ] **Step 1: Write smoke test (`tests/smoke.rs`)**

```rust
//! Pre-condition: PG/Redis/Kafka up; auth-service running on 8001; user-service on 8002.
use reqwest::{Client, StatusCode};
use serde_json::json;
use rdkafka::{consumer::{StreamConsumer, Consumer}, ClientConfig, Message};
use std::time::Duration;

fn cli() -> Client { Client::builder().cookie_store(true).build().unwrap() }
const AUTH:  &str = "http://127.0.0.1:8001";
const USER:  &str = "http://127.0.0.1:8002";

async fn register(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c.post(format!("{AUTH}/api/v1/auth/register"))
        .json(&json!({ "username": format!("u{}", &u[..10]), "email": format!("{u}@e.com"), "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), 200);
    r.json::<serde_json::Value>().await.unwrap()
}

#[tokio::test]
async fn follow_emits_event_and_rejects_self() {
    let a = cli(); let b = cli();
    let ua = register(&a).await; let ub = register(&b).await;
    let ua_id = ua["user"]["id"].as_str().unwrap();
    let ub_id = ub["user"]["id"].as_str().unwrap();

    // self-follow → 400
    let r = a.post(format!("{USER}/api/v1/users/{ua_id}/follow")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);

    // a follows b
    let r = a.post(format!("{USER}/api/v1/users/{ub_id}/follow")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);

    // event landed
    let consumer: StreamConsumer = ClientConfig::new()
        .set("bootstrap.servers", "127.0.0.1:9092")
        .set("group.id", "smoke-user")
        .set("auto.offset.reset", "earliest")
        .create().unwrap();
    consumer.subscribe(&["oecophylla.user.followed"]).unwrap();
    let msg = tokio::time::timeout(Duration::from_secs(5), consumer.recv()).await.unwrap().unwrap();
    let body: serde_json::Value = serde_json::from_slice(msg.payload().unwrap()).unwrap();
    assert_eq!(body["data"]["follower_id"], ua_id);
    assert_eq!(body["data"]["followee_id"], ub_id);
}

#[tokio::test]
async fn put_profile_non_owner_forbidden() {
    let a = cli(); let b = cli();
    let _ua = register(&a).await; let ub = register(&b).await;
    let ub_id = ub["user"]["id"].as_str().unwrap();
    let r = a.put(format!("{USER}/api/v1/users/{ub_id}"))
        .json(&json!({ "display_name": "hax" })).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::FORBIDDEN);
}
```

Add `rdkafka` to `user-service/Cargo.toml [dev-dependencies]`.

- [ ] **Step 2: `state.rs`**

```rust
use common::{config::SharedConfig, kafka::Producer};
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;
use std::sync::Arc;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub kafka: Producer,
    pub cfg: Arc<SharedConfig>,
}
```

- [ ] **Step 3: `repo.rs`**

```rust
use common::error::AppError;
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, serde::Serialize, Clone)]
pub struct ProfileRow {
    pub id: Uuid,
    pub username: String,
    pub display_name: Option<String>,
    pub bio: Option<String>,
    pub avatar_url: Option<String>,
    pub topic_prefs: Vec<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub async fn get_profile(db: &PgPool, id: Uuid) -> Result<Option<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT id, username, display_name, bio, avatar_url, topic_prefs, created_at
         FROM users WHERE id = $1 AND is_active = true").bind(id).fetch_optional(db).await?)
}

pub async fn update_profile(db: &PgPool, id: Uuid, display_name: Option<&str>, bio: Option<&str>, avatar_url: Option<&str>, topic_prefs: Option<&[String]>) -> Result<ProfileRow, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "UPDATE users SET
            display_name = COALESCE($2, display_name),
            bio          = COALESCE($3, bio),
            avatar_url   = COALESCE($4, avatar_url),
            topic_prefs  = COALESCE($5, topic_prefs)
         WHERE id = $1
         RETURNING id, username, display_name, bio, avatar_url, topic_prefs, created_at"
    ).bind(id).bind(display_name).bind(bio).bind(avatar_url).bind(topic_prefs)
     .fetch_one(db).await?)
}

pub async fn insert_follow(db: &PgPool, follower: Uuid, followee: Uuid) -> Result<bool, AppError> {
    let r = sqlx::query(
        "INSERT INTO follows (follower_id, followee_id) VALUES ($1, $2)
         ON CONFLICT DO NOTHING").bind(follower).bind(followee).execute(db).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn delete_follow(db: &PgPool, follower: Uuid, followee: Uuid) -> Result<bool, AppError> {
    let r = sqlx::query("DELETE FROM follows WHERE follower_id=$1 AND followee_id=$2")
        .bind(follower).bind(followee).execute(db).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn list_followers(db: &PgPool, id: Uuid, limit: i64) -> Result<Vec<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT u.id, u.username, u.display_name, u.bio, u.avatar_url, u.topic_prefs, u.created_at
         FROM follows f JOIN users u ON u.id = f.follower_id
         WHERE f.followee_id = $1 ORDER BY f.created_at DESC LIMIT $2")
        .bind(id).bind(limit).fetch_all(db).await?)
}

pub async fn list_following(db: &PgPool, id: Uuid, limit: i64) -> Result<Vec<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT u.id, u.username, u.display_name, u.bio, u.avatar_url, u.topic_prefs, u.created_at
         FROM follows f JOIN users u ON u.id = f.followee_id
         WHERE f.follower_id = $1 ORDER BY f.created_at DESC LIMIT $2")
        .bind(id).bind(limit).fetch_all(db).await?)
}

pub async fn search(db: &PgPool, q: &str, limit: i64) -> Result<Vec<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT id, username, display_name, bio, avatar_url, topic_prefs, created_at
         FROM users
         WHERE is_active = true AND (username ILIKE $1 OR display_name ILIKE $1)
         ORDER BY created_at DESC LIMIT $2")
        .bind(format!("%{q}%")).bind(limit).fetch_all(db).await?)
}
```

- [ ] **Step 4: `handlers.rs`**

```rust
use axum::{extract::{Path, Query, State}, http::StatusCode, response::IntoResponse, Json};
use common::{auth::verify_access, error::{AppError, AppResult}, events::{Envelope, UserFollowed, TOPIC_USER_FOLLOWED}};
use serde::Deserialize;
use uuid::Uuid;

use crate::{state::AppState, repo};

#[derive(Deserialize)] pub struct UpdateProfileReq { pub display_name: Option<String>, pub bio: Option<String>, pub avatar_url: Option<String>, pub topic_prefs: Option<Vec<String>> }
#[derive(Deserialize)] pub struct PageQ  { pub limit: Option<i64> }
#[derive(Deserialize)] pub struct SearchQ { pub q: Option<String>, pub limit: Option<i64> }

fn current_user(s: &AppState, h: &axum::http::HeaderMap) -> Option<common::models::AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw.split(';').find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let c = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(common::models::AuthUser { id: c.sub, role: c.role })
}

pub async fn get(State(s): State<AppState>, Path(id): Path<Uuid>) -> AppResult<Json<repo::ProfileRow>> {
    repo::get_profile(&s.db, id).await?
        .map(Json).ok_or(AppError::NotFound { kind: "user".into() })
}

pub async fn update(State(s): State<AppState>, Path(id): Path<Uuid>, h: axum::http::HeaderMap, Json(body): Json<UpdateProfileReq>) -> AppResult<Json<repo::ProfileRow>> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    if me.id != id { return Err(AppError::Forbidden); }
    let prefs_ref: Option<&[String]> = body.topic_prefs.as_deref();
    let row = repo::update_profile(&s.db, id, body.display_name.as_deref(), body.bio.as_deref(), body.avatar_url.as_deref(), prefs_ref).await?;
    Ok(Json(row))
}

pub async fn follow(State(s): State<AppState>, Path(id): Path<Uuid>, h: axum::http::HeaderMap) -> AppResult<impl IntoResponse> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    if me.id == id { return Err(AppError::Validation { field: "id".into(), message: "cannot follow self".into() }); }
    let created = repo::insert_follow(&s.db, me.id, id).await?;
    if created {
        let env = Envelope::new("user.followed", "user-service", UserFollowed {
            follower_id: me.id, followee_id: id, followed_at: common::time::now() });
        s.kafka.produce_json(TOPIC_USER_FOLLOWED, id.to_string().as_str(), &env).await;
    }
    Ok(StatusCode::CREATED)
}

pub async fn unfollow(State(s): State<AppState>, Path(id): Path<Uuid>, h: axum::http::HeaderMap) -> AppResult<impl IntoResponse> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    repo::delete_follow(&s.db, me.id, id).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn followers(State(s): State<AppState>, Path(id): Path<Uuid>, Query(q): Query<PageQ>) -> AppResult<Json<Vec<repo::ProfileRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_followers(&s.db, id, limit).await?))
}

pub async fn following(State(s): State<AppState>, Path(id): Path<Uuid>, Query(q): Query<PageQ>) -> AppResult<Json<Vec<repo::ProfileRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_following(&s.db, id, limit).await?))
}

pub async fn search_users(State(s): State<AppState>, Query(q): Query<SearchQ>) -> AppResult<Json<Vec<repo::ProfileRow>>> {
    let q_str = q.q.unwrap_or_default();
    if q_str.trim().is_empty() { return Ok(Json(vec![])); }
    let limit = q.limit.unwrap_or(20).clamp(1, 50);
    Ok(Json(repo::search(&s.db, q_str.trim(), limit).await?))
}
```

- [ ] **Step 5: `main.rs`**

```rust
use axum::{Router, routing::{get, post, put, delete}};
use common::{config::SharedConfig, db::pg_pool, redis::redis_pool, kafka::Producer, middleware::trace::init_tracing};
use std::{net::SocketAddr, sync::Arc};

mod state; mod handlers; mod repo;
use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("user-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("USER_BIND").unwrap_or_else(|_| "0.0.0.0:8002".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let state = AppState { db, redis, kafka, cfg: Arc::new(cfg.clone()) };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/api/v1/users",                  get(handlers::search_users))
        .route("/api/v1/users/:id",              get(handlers::get).put(handlers::update))
        .route("/api/v1/users/:id/follow",       post(handlers::follow).delete(handlers::unfollow))
        .route("/api/v1/users/:id/followers",    get(handlers::followers))
        .route("/api/v1/users/:id/following",    get(handlers::following))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "user-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

- [ ] **Step 6: `Dockerfile`** — same template as auth-service, replace `auth-service` with `user-service` and `EXPOSE 8002`.

- [ ] **Step 7: Smoke**

```bash
# from project root
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
cd backend
# start both services in background, then test
(AUTH_BIND=0.0.0.0:8001 DATABASE_URL=... REDIS_URL=... KAFKA_BROKERS=127.0.0.1:9092 JWT_SECRET=... cargo run -p auth-service &)
(USER_BIND=0.0.0.0:8002 ... cargo run -p user-service &)
sleep 5
cargo test -p user-service --test smoke -- --test-threads=1
```

- [ ] **Step 8: Commit**

```bash
git add backend/services/user-service/
git commit -m "feat(user-service): profile/follow/search + user.followed kafka event"
```

---

## Task 10: content-service — posts CRUD + content.created event

**Files:**
- Modify: `backend/services/content-service/src/main.rs`
- Create: `backend/services/content-service/src/{state,handlers,repo}.rs`
- Create: `backend/services/content-service/tests/smoke.rs`
- Create: `backend/services/content-service/Dockerfile`

- [ ] **Step 1: Smoke test (`tests/smoke.rs`)** — 4 cases matching spec §6.2

```rust
use reqwest::{Client, StatusCode};
use serde_json::json;
use rdkafka::{consumer::{StreamConsumer, Consumer}, ClientConfig, Message};
use std::time::Duration;

fn cli() -> Client { Client::builder().cookie_store(true).build().unwrap() }
const AUTH:    &str = "http://127.0.0.1:8001";
const CONTENT: &str = "http://127.0.0.1:8003";

async fn register(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c.post(format!("{AUTH}/api/v1/auth/register"))
        .json(&json!({ "username": format!("u{}", &u[..10]), "email": format!("{u}@e.com"), "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), 200);
    r.json::<serde_json::Value>().await.unwrap()
}

#[tokio::test]
async fn post_create_publishes_event_and_validates() {
    let c = cli();
    let _ = register(&c).await;

    // empty content → 400
    let r = c.post(format!("{CONTENT}/api/v1/posts")).json(&json!({ "content": "" })).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);

    // happy
    let r = c.post(format!("{CONTENT}/api/v1/posts")).json(&json!({ "content": "Hello world", "tags": ["greet"] })).send().await.unwrap();
    assert_eq!(r.status(), 200);
    let post: serde_json::Value = r.json().await.unwrap();
    assert_eq!(post["status"], "published");

    // event arrived
    let consumer: StreamConsumer = ClientConfig::new()
        .set("bootstrap.servers", "127.0.0.1:9092")
        .set("group.id", "smoke-content")
        .set("auto.offset.reset", "earliest")
        .create().unwrap();
    consumer.subscribe(&["oecophylla.content.created"]).unwrap();
    let msg = tokio::time::timeout(Duration::from_secs(5), consumer.recv()).await.unwrap().unwrap();
    let env: serde_json::Value = serde_json::from_slice(msg.payload().unwrap()).unwrap();
    assert_eq!(env["data"]["post_id"], post["id"]);
}

#[tokio::test]
async fn list_by_author_paginates() {
    let c = cli();
    let u = register(&c).await;
    let id = u["user"]["id"].as_str().unwrap();
    for i in 0..3 {
        c.post(format!("{CONTENT}/api/v1/posts")).json(&json!({ "content": format!("p{i}") })).send().await.unwrap();
    }
    let r = c.get(format!("{CONTENT}/api/v1/posts?author_id={id}&limit=10")).send().await.unwrap();
    assert_eq!(r.status(), 200);
    let arr: serde_json::Value = r.json().await.unwrap();
    assert!(arr.as_array().unwrap().len() >= 3);
}

#[tokio::test]
async fn delete_non_owner_forbidden() {
    let a = cli(); let b = cli();
    let _ = register(&a).await; let _ = register(&b).await;
    let r = a.post(format!("{CONTENT}/api/v1/posts")).json(&json!({ "content": "mine" })).send().await.unwrap();
    let post: serde_json::Value = r.json().await.unwrap();
    let pid = post["id"].as_str().unwrap();
    let r = b.delete(format!("{CONTENT}/api/v1/posts/{pid}")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::FORBIDDEN);
}
```

- [ ] **Step 2: `state.rs`** — copy from Task 9 (Db + Redis + Kafka + Cfg).

- [ ] **Step 3: `repo.rs`**

```rust
use common::{error::AppError, ids::new_id, models::PostStatus};
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, serde::Serialize, Clone)]
pub struct PostRow {
    pub id: Uuid,
    pub author_id: Uuid,
    pub content: String,
    pub media_urls: Vec<String>,
    pub tags: Vec<String>,
    pub topics: Vec<String>,
    pub safety_score: f32,
    pub status: PostStatus,
    pub view_count: i64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

pub async fn insert(db: &PgPool, author: Uuid, content: &str, media: &[String], tags: &[String], status: PostStatus) -> Result<PostRow, AppError> {
    let id = new_id();
    Ok(sqlx::query_as::<_, PostRow>(
        "INSERT INTO posts (id, author_id, content, media_urls, tags, status)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, created_at, updated_at"
    ).bind(id).bind(author).bind(content).bind(media).bind(tags).bind(status)
     .fetch_one(db).await?)
}

pub async fn by_id(db: &PgPool, id: Uuid) -> Result<Option<PostRow>, AppError> {
    Ok(sqlx::query_as::<_, PostRow>(
        "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, created_at, updated_at
         FROM posts WHERE id = $1").bind(id).fetch_optional(db).await?)
}

pub async fn list_by_author(db: &PgPool, author: Uuid, limit: i64) -> Result<Vec<PostRow>, AppError> {
    Ok(sqlx::query_as::<_, PostRow>(
        "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, created_at, updated_at
         FROM posts WHERE author_id = $1 AND status = 'published'
         ORDER BY created_at DESC LIMIT $2").bind(author).bind(limit).fetch_all(db).await?)
}

pub async fn delete(db: &PgPool, id: Uuid) -> Result<bool, AppError> {
    Ok(sqlx::query("DELETE FROM posts WHERE id = $1").bind(id).execute(db).await?.rows_affected() == 1)
}

pub async fn increment_view(db: &PgPool, id: Uuid) -> Result<(), AppError> {
    sqlx::query("UPDATE posts SET view_count = view_count + 1 WHERE id = $1").bind(id).execute(db).await?;
    Ok(())
}
```

- [ ] **Step 4: `handlers.rs`**

```rust
use axum::{extract::{Path, Query, State}, http::StatusCode, response::IntoResponse, Json};
use common::{auth::verify_access, error::{AppError, AppResult}, events::{Envelope, ContentCreated, TOPIC_CONTENT_CREATED}, models::{AuthUser, PostStatus, UserRole}};
use serde::Deserialize;
use uuid::Uuid;

use crate::{state::AppState, repo};

#[derive(Deserialize)]
pub struct CreatePostReq {
    pub content: String,
    #[serde(default)] pub media_urls: Vec<String>,
    #[serde(default)] pub tags: Vec<String>,
}
#[derive(Deserialize)] pub struct ListQ { pub author_id: Option<Uuid>, pub limit: Option<i64> }

fn current(s: &AppState, h: &axum::http::HeaderMap) -> Option<AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw.split(';').find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let c = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(AuthUser { id: c.sub, role: c.role })
}

pub async fn create(State(s): State<AppState>, h: axum::http::HeaderMap, Json(body): Json<CreatePostReq>) -> AppResult<Json<repo::PostRow>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let content = body.content.trim();
    if content.is_empty() || content.chars().count() > 4000 {
        return Err(AppError::Validation { field: "content".into(), message: "1..=4000 chars".into() });
    }
    if body.media_urls.len() > 6 || body.media_urls.iter().any(|u| !u.starts_with("https://")) {
        return Err(AppError::Validation { field: "media_urls".into(), message: "<=6 https urls".into() });
    }
    if body.tags.len() > 8 {
        return Err(AppError::Validation { field: "tags".into(), message: "<=8 tags".into() });
    }
    let status = if s.cfg.auto_publish { PostStatus::Published } else { PostStatus::Pending };
    let row = repo::insert(&s.db, me.id, content, &body.media_urls, &body.tags, status).await?;
    let env = Envelope::new("content.created", "content-service", ContentCreated {
        post_id: row.id, author_id: row.author_id, content: row.content.clone(),
        tags: row.tags.clone(), created_at: row.created_at });
    s.kafka.produce_json(TOPIC_CONTENT_CREATED, row.id.to_string().as_str(), &env).await;
    Ok(Json(row))
}

pub async fn get_one(State(s): State<AppState>, Path(id): Path<Uuid>) -> AppResult<Json<repo::PostRow>> {
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound { kind: "post".into() })?;
    Ok(Json(row))
}

pub async fn list(State(s): State<AppState>, Query(q): Query<ListQ>) -> AppResult<Json<Vec<repo::PostRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let author = q.author_id.ok_or(AppError::Validation { field: "author_id".into(), message: "required".into() })?;
    Ok(Json(repo::list_by_author(&s.db, author, limit).await?))
}

pub async fn delete_post(State(s): State<AppState>, Path(id): Path<Uuid>, h: axum::http::HeaderMap) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound { kind: "post".into() })?;
    if row.author_id != me.id && me.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    repo::delete(&s.db, id).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn view(State(s): State<AppState>, Path(id): Path<Uuid>) -> AppResult<impl IntoResponse> {
    repo::increment_view(&s.db, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
```

- [ ] **Step 5: `main.rs`**

```rust
use axum::{Router, routing::{get, post, delete}};
use common::{config::SharedConfig, db::pg_pool, redis::redis_pool, kafka::Producer, middleware::trace::init_tracing};
use std::{net::SocketAddr, sync::Arc};

mod state; mod handlers; mod repo;
use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("content-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("CONTENT_BIND").unwrap_or_else(|_| "0.0.0.0:8003".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let state = AppState { db, redis, kafka, cfg: Arc::new(cfg.clone()) };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/api/v1/posts",          post(handlers::create).get(handlers::list))
        .route("/api/v1/posts/:id",      get(handlers::get_one).delete(handlers::delete_post))
        .route("/api/v1/posts/:id/view", post(handlers::view))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "content-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

- [ ] **Step 6: `Dockerfile`** — same template, `content-service`, `EXPOSE 8003`.

- [ ] **Step 7: Run smoke**

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
(cargo run -p auth-service &) && (cargo run -p user-service &) && (cargo run -p content-service &)
sleep 6
cargo test -p content-service --test smoke -- --test-threads=1
```

- [ ] **Step 8: Commit**

```bash
git add backend/services/content-service/
git commit -m "feat(content-service): posts CRUD + content.created kafka event"
```

---

## Task 11: Envoy live end-to-end smoke

**Files:** none new — just verify routing.

- [ ] **Step 1: Bring up full backend via compose**

```bash
docker compose up -d --build
docker compose ps
```
Expected: all services healthy.

- [ ] **Step 2: Hit Envoy and verify routing**

```bash
# Register through Envoy
curl -v -c cookies.txt -X POST http://localhost:8080/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice1","email":"alice1@example.com","password":"Password!123"}'

# Me
curl -s -b cookies.txt http://localhost:8080/api/v1/auth/me | python3 -m json.tool

# Create post
curl -s -b cookies.txt -X POST http://localhost:8080/api/v1/posts \
  -H 'Content-Type: application/json' \
  -d '{"content":"hello from envoy"}' | python3 -m json.tool
```
Expected: 200/200/200 with proper JSON; `Set-Cookie` returned on register.

- [ ] **Step 3: Verify Kafka received event**

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic oecophylla.content.created --from-beginning --max-messages 1 --timeout-ms 5000
```
Expected: one JSON event with `event_type: content.created`.

- [ ] **Step 4: Commit** (no code change — log the verification)

```bash
git commit --allow-empty -m "test(infra): full backend end-to-end smoke through envoy"
```

---

## Task 12: SvelteKit scaffold + Tailwind + tokens

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-workspace.yaml` (empty file to anchor pnpm)
- Create: `frontend/svelte.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.cjs`
- Create: `frontend/postcss.config.cjs`
- Create: `frontend/tsconfig.json`
- Create: `frontend/.npmrc`
- Create: `frontend/src/app.html`
- Create: `frontend/src/app.css`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: `package.json`**

```json
{
  "name": "oecophylla-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite dev --port 3000",
    "build": "vite build",
    "preview": "vite preview --port 3000",
    "start": "node build",
    "lint": "eslint .",
    "test": "vitest run",
    "check": "svelte-kit sync && svelte-check"
  },
  "devDependencies": {
    "@sveltejs/adapter-node": "^5.2.0",
    "@sveltejs/kit": "^2.8.0",
    "@sveltejs/vite-plugin-svelte": "^4.0.0",
    "@types/node": "^22.0.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.13.0",
    "postcss": "^8.4.49",
    "svelte": "^5.0.0",
    "svelte-check": "^4.0.0",
    "tailwindcss": "^3.4.14",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Configs**

`svelte.config.js`:
```js
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
export default {
  preprocess: vitePreprocess(),
  kit: { adapter: adapter() }
};
```

`vite.config.ts`:
```ts
import { sveltekit } from '@sveltejs/kit/vite';
export default { plugins: [sveltekit()] };
```

`tsconfig.json`:
```json
{ "extends": "./.svelte-kit/tsconfig.json", "compilerOptions": { "strict": true, "moduleResolution": "bundler" } }
```

`postcss.config.cjs`:
```js
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`tailwind.config.cjs` — port tokens from `styles/tokens.css`:
```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        ink:    { 900: '#0F1413', 800: '#1E2625', 700: '#2E3837', 500: '#5E6968' },
        canvas: { 50:  '#FAFAF6', 100: '#F2F0E8' },
        accent: { 500: '#0F8C5A', 600: '#0B6F47' },
      },
      fontFamily: {
        sans:    ['"Be Vietnam Pro"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Lora', 'ui-serif', 'serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: { glass: '20px', chip: '999px' },
      boxShadow: {
        glass:    '0 1px 0 rgba(255,255,255,0.4) inset, 0 8px 30px rgba(15,20,19,0.08)',
        glassLg:  '0 1px 0 rgba(255,255,255,0.5) inset, 0 16px 50px rgba(15,20,19,0.12)',
      },
      backdropBlur: { glass: '20px' },
    },
  },
  plugins: [],
};
```

`.npmrc`:
```
engine-strict=true
```

- [ ] **Step 3: `src/app.html`**

```html
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    %sveltekit.head%
  </head>
  <body class="bg-canvas-50 text-ink-900 font-sans antialiased">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
```

- [ ] **Step 4: `src/app.css`** — recipes for repeated patterns

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .glass-surface {
    @apply bg-canvas-50/65 backdrop-blur-glass border border-white/40
           rounded-glass shadow-glass;
  }
  .glass-chip {
    @apply inline-flex items-center gap-1.5 px-3 py-1 text-sm
           rounded-chip glass-surface;
  }
  .glass-pill {
    @apply inline-flex items-center gap-2 px-4 py-2 rounded-chip
           bg-ink-900 text-canvas-50 hover:bg-ink-800 transition-colors;
  }
  .glass-button-primary {
    @apply glass-pill bg-accent-500 hover:bg-accent-600;
  }
  .text-display-serif { @apply font-display italic font-medium; }
  .text-mono-meta     { @apply font-mono text-xs text-ink-500; }
}
```

- [ ] **Step 5: `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:22-trixie-slim AS builder
WORKDIR /app
RUN corepack enable
COPY pnpm-lock.yaml package.json ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-trixie-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
COPY --from=builder /app/package.json /app/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --prod
COPY --from=builder /app/build ./build
EXPOSE 3000
CMD ["node", "build"]
```

- [ ] **Step 6: Install + bring up**

```bash
cd /Users/nhathaminh/oecophylla/frontend
pnpm install
pnpm svelte-kit sync
pnpm build
```
Expected: `build/` directory present.

- [ ] **Step 7: Commit**

```bash
cd /Users/nhathaminh/oecophylla
git add frontend/
git commit -m "feat(frontend): sveltekit scaffold, tailwind tokens, glass recipes"
```

---

## Task 13: Frontend lib — api.ts, hooks.server.ts, auth store

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks.server.ts`
- Create: `frontend/src/lib/stores/auth.ts`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: `src/lib/types.ts`**

```ts
export type UserRole = 'user' | 'creator' | 'admin';
export type PostStatus = 'pending' | 'published' | 'hidden' | 'flagged';

export interface User { id: string; username: string; email: string; role: UserRole; display_name: string | null; avatar_url: string | null; }
export interface Profile extends User { bio: string | null; topic_prefs: string[]; created_at: string; }
export interface Post { id: string; author_id: string; content: string; media_urls: string[]; tags: string[]; topics: string[]; safety_score: number; status: PostStatus; view_count: number; created_at: string; updated_at: string; }
export interface ApiError { error: { code: string; message: string; details?: unknown }; }
```

- [ ] **Step 2: `src/lib/api.ts`**

```ts
import type { ApiError } from './types';

export class ApiException extends Error {
  constructor(public status: number, public code: string, public details?: unknown) {
    super(`${status} ${code}`);
  }
}

export type Fetch = typeof fetch;

export async function apiFetch<T>(fetchImpl: Fetch, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetchImpl(`/api/v1${path}`, {
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      'x-requested-with': 'oec-web',
      ...(init.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    let body: ApiError | null = null;
    try { body = await res.json(); } catch {}
    throw new ApiException(res.status, body?.error.code ?? 'UNKNOWN', body?.error.details);
  }
  if (res.status === 204) return undefined as T;
  return await res.json() as T;
}
```

- [ ] **Step 3: `src/hooks.server.ts`** — server-side proxy to Envoy + auto refresh

```ts
import type { Handle, HandleFetch } from '@sveltejs/kit';

const ENVOY = process.env.ENVOY_URL ?? 'http://envoy:8080';

export const handle: Handle = async ({ event, resolve }) => {
  // Forward server-side `event.fetch` of /api/v1/* to the gateway.
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/v1/')) {
    const upstream = new URL(url.pathname + url.search, ENVOY);
    const headers = new Headers(request.headers);
    // Forward cookies sent by the browser through SSR
    const cookie = event.request.headers.get('cookie');
    if (cookie) headers.set('cookie', cookie);
    headers.set('x-requested-with', 'oec-web');
    const resp = await fetch(new Request(upstream, { method: request.method, headers, body: request.body, credentials: 'include', redirect: 'manual' }));
    // Propagate Set-Cookie to the browser via the page response
    const setCookie = resp.headers.get('set-cookie');
    if (setCookie) event.cookies.set('__forward__', '1', { path: '/' }); // sentinel; real cookies flow via the fetch response below
    return resp;
  }
  return fetch(request);
};
```

> Note: with adapter-node, SvelteKit's server `fetch` returns the upstream response complete with `Set-Cookie` headers; the browser sees them via the page response. `handleFetch` only needs to rewrite the URL and forward the cookie header.

- [ ] **Step 4: `src/lib/stores/auth.ts`**

```ts
import { writable } from 'svelte/store';
import type { User } from '../types';

export const user = writable<User | null>(null);
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nhathaminh/oecophylla
git add frontend/src/{lib,hooks.server.ts}
git commit -m "feat(frontend): api fetch wrapper, SSR fetch proxy to envoy, auth store"
```

---

## Task 14: Frontend — auth pages (login, register, logout)

**Files:**
- Create: `frontend/src/routes/+layout.svelte`
- Create: `frontend/src/routes/+layout.server.ts`
- Create: `frontend/src/routes/login/+page.svelte`
- Create: `frontend/src/routes/login/+page.server.ts`
- Create: `frontend/src/routes/register/+page.svelte`
- Create: `frontend/src/routes/register/+page.server.ts`
- Create: `frontend/src/routes/logout/+server.ts`
- Create: `frontend/src/lib/components/AuthForm.svelte`
- Create: `frontend/src/lib/components/Topbar.svelte`

- [ ] **Step 1: `+layout.server.ts`** — hydrate `user` from `/auth/me`

```ts
import type { LayoutServerLoad } from './$types';
import { apiFetch } from '$lib/api';
import type { User } from '$lib/types';

export const load: LayoutServerLoad = async ({ fetch }) => {
  try {
    const body = await apiFetch<{ user: User }>(fetch, '/auth/me');
    return { user: body.user };
  } catch {
    return { user: null };
  }
};
```

- [ ] **Step 2: `+layout.svelte`** — set the store + render shell

```svelte
<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { user } from '$lib/stores/auth';
  import Topbar from '$lib/components/Topbar.svelte';
  export let data: { user: import('$lib/types').User | null };
  $: user.set(data.user);
</script>
<div class="min-h-screen flex flex-col">
  <Topbar />
  <main class="flex-1 max-w-3xl w-full mx-auto p-4">
    <slot />
  </main>
</div>
```

- [ ] **Step 3: `Topbar.svelte`** — glass surface example

```svelte
<script lang="ts">
  import { user } from '$lib/stores/auth';
</script>
<header class="sticky top-3 mx-auto max-w-3xl glass-surface flex items-center justify-between px-5 py-3 mt-3">
  <a href="/" class="text-display-serif text-2xl">Oecophylla</a>
  <nav class="flex items-center gap-2">
    {#if $user}
      <a class="glass-chip" href="/profile/{$user.id}">{$user.display_name ?? $user.username}</a>
      <form method="post" action="/logout"><button class="glass-pill" type="submit">Đăng xuất</button></form>
    {:else}
      <a class="glass-chip" href="/login">Đăng nhập</a>
      <a class="glass-button-primary" href="/register">Đăng ký</a>
    {/if}
  </nav>
</header>
```

- [ ] **Step 4: `AuthForm.svelte`**

```svelte
<script lang="ts">
  export let mode: 'login' | 'register';
  export let error: string | null = null;
</script>
<section class="glass-surface p-6 mt-8 max-w-md mx-auto">
  <h1 class="text-display-serif text-3xl mb-4">{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1>
  <form method="post" class="flex flex-col gap-3">
    {#if mode === 'register'}
      <label class="text-sm">Username
        <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name="username" required />
      </label>
      <label class="text-sm">Tên hiển thị
        <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name="display_name" />
      </label>
    {/if}
    <label class="text-sm">{mode === 'login' ? 'Email hoặc username' : 'Email'}
      <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name={mode === 'login' ? 'email_or_username' : 'email'} required />
    </label>
    <label class="text-sm">Mật khẩu
      <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" type="password" name="password" required />
    </label>
    {#if error}<p class="text-red-700 text-sm">{error}</p>{/if}
    <button class="glass-button-primary mt-2" type="submit">{mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}</button>
  </form>
</section>
```

- [ ] **Step 5: `login/+page.svelte`** + `login/+page.server.ts`

`login/+page.svelte`:
```svelte
<script lang="ts">
  import AuthForm from '$lib/components/AuthForm.svelte';
  export let form: { error?: string } | null;
</script>
<AuthForm mode="login" error={form?.error ?? null} />
```

`login/+page.server.ts`:
```ts
import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const data = await request.formData();
    try {
      await apiFetch(fetch, '/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email_or_username: String(data.get('email_or_username') ?? ''),
          password: String(data.get('password') ?? ''),
        }),
      });
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) return fail(401, { error: 'Sai thông tin đăng nhập' });
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
```

- [ ] **Step 6: `register/+page.svelte`** + `register/+page.server.ts`

`register/+page.svelte`:
```svelte
<script lang="ts">
  import AuthForm from '$lib/components/AuthForm.svelte';
  export let form: { error?: string } | null;
</script>
<AuthForm mode="register" error={form?.error ?? null} />
```

`register/+page.server.ts`:
```ts
import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const f = await request.formData();
    try {
      await apiFetch(fetch, '/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: String(f.get('username') ?? ''),
          email: String(f.get('email') ?? ''),
          password: String(f.get('password') ?? ''),
          display_name: (f.get('display_name') as string) || null,
        }),
      });
    } catch (e) {
      if (e instanceof ApiException) {
        if (e.status === 409) return fail(409, { error: 'Username hoặc email đã tồn tại' });
        if (e.status === 400) return fail(400, { error: 'Thông tin không hợp lệ' });
      }
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
```

- [ ] **Step 7: `logout/+server.ts`**

```ts
import type { RequestHandler } from './$types';
import { redirect } from '@sveltejs/kit';
import { apiFetch } from '$lib/api';

export const POST: RequestHandler = async ({ fetch }) => {
  try { await apiFetch(fetch, '/auth/logout', { method: 'DELETE' }); } catch {}
  throw redirect(303, '/login');
};
```

- [ ] **Step 8: Manual verify**

```bash
docker compose up -d --build frontend
open http://localhost:3000/register
```
Register, confirm cookie set, redirected to `/`, topbar shows username, click logout, back to `/login`.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/{routes,lib/components}
git commit -m "feat(frontend): login/register/logout pages with glass topbar"
```

---

## Task 15: Frontend — profile + post pages (live-backed)

**Files:**
- Create: `frontend/src/routes/profile/[id]/+page.svelte`
- Create: `frontend/src/routes/profile/[id]/+page.server.ts`
- Create: `frontend/src/routes/post/new/+page.svelte`
- Create: `frontend/src/routes/post/new/+page.server.ts`
- Create: `frontend/src/routes/post/[id]/+page.svelte`
- Create: `frontend/src/routes/post/[id]/+page.server.ts`
- Create: `frontend/src/lib/components/PostCard.svelte`
- Create: `frontend/src/lib/components/Composer.svelte`

- [ ] **Step 1: `PostCard.svelte`**

```svelte
<script lang="ts">
  import type { Post } from '$lib/types';
  export let post: Post;
</script>
<article class="glass-surface p-5 mb-3">
  <p class="whitespace-pre-wrap">{post.content}</p>
  <div class="mt-3 flex items-center gap-2 text-mono-meta">
    <span>{new Date(post.created_at).toLocaleString('vi-VN')}</span>
    {#each post.tags as t}<span class="glass-chip">#{t}</span>{/each}
  </div>
</article>
```

- [ ] **Step 2: `Composer.svelte`**

```svelte
<script lang="ts">
  export let action = '/post/new';
  export let error: string | null = null;
</script>
<form method="post" action={action} class="glass-surface p-5 mb-4">
  <textarea name="content" rows="3" maxlength="4000" placeholder="Bạn đang nghĩ gì?"
    class="w-full bg-transparent outline-none resize-none placeholder:text-ink-500"></textarea>
  <input name="tags" placeholder="thẻ, ngăn cách bởi dấu phẩy" class="block w-full mt-2 px-3 py-2 rounded-xl bg-white/60 border border-white/60 text-sm" />
  {#if error}<p class="text-red-700 text-sm mt-2">{error}</p>{/if}
  <div class="mt-3 flex justify-end"><button class="glass-button-primary" type="submit">Đăng</button></div>
</form>
```

- [ ] **Step 3: `profile/[id]/+page.server.ts`**

```ts
import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Profile, Post } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  try {
    const profile = await apiFetch<Profile>(fetch, `/users/${params.id}`);
    const posts   = await apiFetch<Post[]>(fetch, `/posts?author_id=${params.id}&limit=20`);
    return { profile, posts };
  } catch (e) {
    if (e instanceof ApiException && e.status === 404) throw error(404, 'User not found');
    throw e;
  }
};
```

- [ ] **Step 4: `profile/[id]/+page.svelte`**

```svelte
<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  import { user } from '$lib/stores/auth';
  import { ApiException, apiFetch } from '$lib/api';
  export let data: { profile: import('$lib/types').Profile; posts: import('$lib/types').Post[] };
  let following = false;
  async function toggleFollow() {
    try {
      if (following) await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'DELETE' });
      else           await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'POST' });
      following = !following;
    } catch (e) { if (e instanceof ApiException && e.status === 400) alert('Không thể follow chính mình'); }
  }
</script>

<section class="glass-surface p-6 mb-4">
  <h1 class="text-display-serif text-3xl">{data.profile.display_name ?? data.profile.username}</h1>
  <p class="text-mono-meta">@{data.profile.username} · từ {new Date(data.profile.created_at).toLocaleDateString('vi-VN')}</p>
  {#if data.profile.bio}<p class="mt-2">{data.profile.bio}</p>{/if}
  {#if $user && $user.id !== data.profile.id}
    <button class="glass-pill mt-3" on:click={toggleFollow}>{following ? 'Đang theo dõi' : 'Theo dõi'}</button>
  {/if}
</section>

{#each data.posts as p (p.id)}<PostCard post={p} />{/each}
{#if data.posts.length === 0}<p class="text-ink-500">Chưa có bài viết.</p>{/if}
```

- [ ] **Step 5: `post/new/+page.svelte`** + `+page.server.ts`

`+page.svelte`:
```svelte
<script lang="ts">
  import Composer from '$lib/components/Composer.svelte';
  export let form: { error?: string } | null;
</script>
<Composer error={form?.error ?? null} />
```

`+page.server.ts`:
```ts
import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';
import type { Post } from '$lib/types';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const f = await request.formData();
    const tags = String(f.get('tags') ?? '').split(',').map(s => s.trim()).filter(Boolean);
    try {
      const post = await apiFetch<Post>(fetch, '/posts', {
        method: 'POST',
        body: JSON.stringify({ content: String(f.get('content') ?? ''), tags }),
      });
      throw redirect(303, `/post/${post.id}`);
    } catch (e) {
      if (e instanceof ApiException && e.status === 400) return fail(400, { error: 'Nội dung không hợp lệ' });
      if (e instanceof ApiException && e.status === 401) throw redirect(303, '/login');
      throw e;
    }
  },
};
```

- [ ] **Step 6: `post/[id]/+page.svelte`** + `+page.server.ts`

`+page.server.ts`:
```ts
import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Post } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  try {
    const post = await apiFetch<Post>(fetch, `/posts/${params.id}`);
    await apiFetch(fetch, `/posts/${params.id}/view`, { method: 'POST' }).catch(() => {});
    return { post };
  } catch (e) {
    if (e instanceof ApiException && e.status === 404) throw error(404, 'Post not found');
    throw e;
  }
};
```

`+page.svelte`:
```svelte
<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  export let data: { post: import('$lib/types').Post };
</script>
<PostCard post={data.post} />
```

- [ ] **Step 7: Manual verify**

Boot stack, log in, navigate to `/post/new`, create a post, expect redirect to `/post/<id>`. Open `/profile/<your_id>`, see the post listed. Open as another user, click follow, verify Envoy returns 201 (DevTools network tab).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/{routes,lib/components}
git commit -m "feat(frontend): profile, post create, post detail pages live-backed"
```

---

## Task 16: Frontend — Feed / Admin / Mobile pages (mock-backed)

**Files:**
- Create: `frontend/src/lib/mock/feed.ts`
- Create: `frontend/src/lib/mock/admin.ts`
- Create: `frontend/src/routes/+page.svelte`
- Create: `frontend/src/routes/admin/+page.svelte`
- Create: `frontend/src/routes/m/+page.svelte`
- Create: `frontend/src/lib/components/Sidebar.svelte`
- Create: `frontend/src/lib/components/MobileShell.svelte`

- [ ] **Step 1: `lib/mock/feed.ts`**

```ts
import type { Post } from '$lib/types';
export const mockFeed: Post[] = Array.from({ length: 8 }).map((_, i) => ({
  id: `mock-${i}`, author_id: 'mock-author', content: `Đây là bài viết giả lập #${i + 1}.`,
  media_urls: [], tags: ['demo'], topics: ['tech'], safety_score: 1, status: 'published',
  view_count: 100 + i, created_at: new Date(Date.now() - i * 3.6e6).toISOString(), updated_at: new Date().toISOString(),
}));
```

- [ ] **Step 2: `lib/mock/admin.ts`**

```ts
export const mockReports = [
  { id: 'r1', post_id: 'p1', reason: 'spam', status: 'pending', created_at: new Date().toISOString() },
  { id: 'r2', post_id: 'p2', reason: 'misinformation', status: 'pending', created_at: new Date().toISOString() },
];
export const mockMetrics = { users: 50, posts: 100, reports_pending: 2, ctr: 0.14 };
```

- [ ] **Step 3: `Sidebar.svelte`** — used in feed page (desktop only)

```svelte
<aside class="hidden md:block w-64 sticky top-24 self-start">
  <nav class="glass-surface p-4 flex flex-col gap-2">
    <a class="glass-chip" href="/">Bảng tin</a>
    <a class="glass-chip" href="/post/new">Viết bài</a>
    <a class="glass-chip" href="/admin">Quản trị</a>
    <a class="glass-chip" href="/m">Mobile</a>
  </nav>
</aside>
```

- [ ] **Step 4: `+page.svelte` (Feed, mock)**

```svelte
<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import { mockFeed } from '$lib/mock/feed';
</script>
<div class="grid grid-cols-1 md:grid-cols-[1fr_16rem] gap-6">
  <section>
    <p class="text-mono-meta mb-3">(Phase 1 — feed sử dụng dữ liệu mẫu. Phase 2 sẽ kết nối recommendation-api.)</p>
    {#each mockFeed as p (p.id)}<PostCard post={p} />{/each}
  </section>
  <Sidebar />
</div>
```

- [ ] **Step 5: `admin/+page.svelte`**

```svelte
<script lang="ts">
  import { mockReports, mockMetrics } from '$lib/mock/admin';
</script>
<h1 class="text-display-serif text-3xl mb-3">Quản trị (mock)</h1>
<section class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
  {#each Object.entries(mockMetrics) as [k, v]}
    <div class="glass-surface p-4">
      <p class="text-mono-meta">{k}</p>
      <p class="text-2xl text-display-serif">{v}</p>
    </div>
  {/each}
</section>
<section class="glass-surface p-4">
  <h2 class="text-display-serif text-xl mb-3">Báo cáo đang chờ</h2>
  <ul class="divide-y divide-white/40">
    {#each mockReports as r (r.id)}
      <li class="py-3 flex justify-between">
        <span>{r.reason} · {r.post_id}</span>
        <span class="text-mono-meta">{r.status}</span>
      </li>
    {/each}
  </ul>
</section>
```

- [ ] **Step 6: `MobileShell.svelte`** + `m/+page.svelte`

`MobileShell.svelte`:
```svelte
<div class="md:hidden glass-surface fixed bottom-3 left-3 right-3 flex justify-around py-3">
  <a class="glass-chip" href="/">Feed</a>
  <a class="glass-chip" href="/post/new">Viết</a>
  <a class="glass-chip" href="/admin">Quản trị</a>
</div>
```

`m/+page.svelte`:
```svelte
<script lang="ts">
  import MobileShell from '$lib/components/MobileShell.svelte';
  import { mockFeed } from '$lib/mock/feed';
  import PostCard from '$lib/components/PostCard.svelte';
</script>
<h1 class="text-display-serif text-2xl mb-3">Mobile preview</h1>
{#each mockFeed.slice(0, 3) as p (p.id)}<PostCard post={p} />{/each}
<MobileShell />
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/{routes,lib}
git commit -m "feat(frontend): feed/admin/mobile pages with mock data (live wiring in phase 2/3)"
```

---

## Task 17: Frontend lib/api unit tests (vitest)

**Files:**
- Create: `frontend/src/lib/api.test.ts`
- Modify: `frontend/package.json` (vitest config inline)

- [ ] **Step 1: Add `vitest` config and test**

`frontend/vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { environment: 'node' } });
```

`frontend/src/lib/api.test.ts`:
```ts
import { describe, it, expect, vi } from 'vitest';
import { apiFetch, ApiException } from './api';

describe('apiFetch', () => {
  it('sends credentials and x-requested-with', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' }}));
    await apiFetch(fetchMock as any, '/auth/me');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe('include');
    expect((init.headers as any)['x-requested-with']).toBe('oec-web');
  });

  it('throws ApiException with envelope code on non-2xx', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ error: { code: 'CONFLICT', message: 'dup' }}), { status: 409, headers: { 'content-type': 'application/json' }}));
    await expect(apiFetch(fetchMock as any, '/x')).rejects.toMatchObject({ status: 409, code: 'CONFLICT' });
  });

  it('returns undefined on 204', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    const v = await apiFetch(fetchMock as any, '/logout', { method: 'DELETE' });
    expect(v).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run vitest**

```bash
cd /Users/nhathaminh/oecophylla/frontend
pnpm vitest run
```
Expected: 3 passing.

- [ ] **Step 3: Commit**

```bash
git add frontend/{src/lib/api.test.ts,vitest.config.ts}
git commit -m "test(frontend): api fetch wrapper unit tests"
```

---

## Task 18: Seed Phase 1 script

**Files:**
- Create: `scripts/seed_phase1.py`
- Create: `scripts/requirements.txt`
- Create: `scripts/Dockerfile`
- Create: `scripts/seed_phase1_compose.yaml` (override fragment) — alternatively add a `scripts` service to `compose.yaml`

- [ ] **Step 1: `requirements.txt`**

```
psycopg[binary]==3.2.3
argon2-cffi==23.1.0
```

- [ ] **Step 2: `Dockerfile`**

```dockerfile
FROM python:3.13-trixie
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt
COPY . /app
ENTRYPOINT ["python"]
```

- [ ] **Step 3: Add `scripts` service to `compose.yaml`**

```yaml
  scripts:
    profiles: ["tools"]
    build: ./scripts
    depends_on:
      postgres: { condition: service_healthy }
    environment:
      DATABASE_URL: ${DATABASE_URL}
```

- [ ] **Step 4: `scripts/seed_phase1.py`**

```python
"""Seed Phase 1 data: 50 users, 100 posts, 200 follows."""
import os
import random
import secrets
import sys
from argon2 import PasswordHasher
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]
SHARED_HASH = PasswordHasher().hash("Password!123")  # computed once

random.seed(20260525)

def main():
    with psycopg.connect(DATABASE_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM users")
            (n,) = cur.fetchone()
            if n > 0:
                print(f"users table not empty ({n} rows); aborting", file=sys.stderr)
                sys.exit(2)

            roles = ["admin"] * 3 + ["creator"] * 7 + ["user"] * 40
            user_ids = []
            for i, role in enumerate(roles):
                username = f"seed_{i:03d}"
                email = f"{username}@oec.local"
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, role, display_name)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (username, email, SHARED_HASH, role, f"Seed User {i:03d}"),
                )
                user_ids.append(cur.fetchone()[0])

            topics_pool = ["tech","science","sports","politics","entertainment","health","business","culture","education","environment"]
            for i in range(100):
                author = random.choice(user_ids)
                topics = random.sample(topics_pool, k=random.randint(1, 3))
                cur.execute(
                    """INSERT INTO posts (author_id, content, tags, topics, status)
                       VALUES (%s, %s, %s, %s, 'published')""",
                    (author, f"Seeded post #{i} about {topics[0]}", topics, topics),
                )

            edges = set()
            while len(edges) < 200:
                a, b = random.sample(user_ids, 2)
                edges.add((a, b))
            for a, b in edges:
                cur.execute("INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (a, b))

        conn.commit()
    print(f"Seeded: {len(user_ids)} users, 100 posts, 200 follows")

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run + verify**

```bash
docker compose --profile tools build scripts
docker compose --profile tools run --rm scripts seed_phase1.py
docker compose exec postgres psql -U oecophylla -d oecophylla -c "SELECT count(*) FROM users; SELECT count(*) FROM posts; SELECT count(*) FROM follows;"
```
Expected: 50 / 100 / 200.

- [ ] **Step 6: Commit**

```bash
git add scripts/ compose.yaml
git commit -m "feat(seed): phase-1 seed script (50 users, 100 posts, 200 follows)"
```

---

## Task 19: Root Makefile + README

**Files:**
- Create: `Makefile`
- Create: `README.md`

- [ ] **Step 1: `Makefile`** — copy spec §7.1 verbatim.

- [ ] **Step 2: `README.md`**

```markdown
# Oecophylla

Social network with intelligent news feed recommendation and multi-layer content moderation.
Phase 0+1 (foundation + identity + content) — see `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md`.

## Quick start

```bash
cp .env.example .env
make up
make seed   # optional — 50 users / 100 posts / 200 follows
```

Browse:
- Frontend: http://localhost:3000
- Envoy API gateway: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin / password from `.env`)

## Service URLs (dev override exposes raw ports)

| Service | Internal | Host-exposed via `compose.dev.yaml` |
|---|---|---|
| auth-service | http://auth-service:8001 | http://localhost:8001 |
| user-service | http://user-service:8002 | http://localhost:8002 |
| content-service | http://content-service:8003 | http://localhost:8003 |
| postgres | postgres:5432 | localhost:5432 |
| redis | redis:6379 | localhost:6379 |
| kafka | kafka:9092 | localhost:9092 |

## Smoke tests

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
cd backend && cargo run -p auth-service & cargo run -p user-service & cargo run -p content-service &
sleep 5
make test
```

## Layout

```
backend/  Cargo workspace — auth, user, content services + common crate
frontend/ SvelteKit (adapter-node) + Tailwind, Apple Glass UI port
envoy/    Gateway config
infra/    Prometheus + Grafana provisioning, Kafka init script
migrations/  sqlx migrations (shared schema)
scripts/  Seed + utility Python
docs/superpowers/{specs,plans}/  Design docs + implementation plans
```

## What is in Phase 0+1 and what is not

Phase 0+1 ships: PG 18 + Redis 7 + Kafka 4 KRaft + Envoy + 3 Rust services + SvelteKit
frontend. Auth, profile, follow, post-create and post-detail are wired end-to-end.
Feed, admin, and mobile pages render with mock data. Recommendation, interactions,
moderation, notifications, analytics belong to Phase 2-4.
```

- [ ] **Step 3: Commit**

```bash
git add Makefile README.md
git commit -m "docs: root README + makefile"
```

---

## Task 20: Final manual verify against Definition of Done

**Files:** none — execute spec §6.4 checklist.

- [ ] **Step 1: Cold boot**

```bash
make clean
time make up
```
Expected: all services healthy ≤ 90s.

- [ ] **Step 2: Migrate idempotency**

```bash
docker compose up migrate
docker compose up migrate   # second run
```
Expected: second run reports "no migrations to run".

- [ ] **Step 3: `make test`** — all tests pass.

- [ ] **Step 4: `make seed`** — populates 50 / 100 / 200.

- [ ] **Step 5: Browse manual flows** — register, login, create post, view profile, follow user. Verify Kafka events:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic oecophylla.content.created --from-beginning --max-messages 1 --timeout-ms 3000
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic oecophylla.user.followed --from-beginning --max-messages 1 --timeout-ms 3000
```

- [ ] **Step 6: Lint clean**

```bash
make lint
```

- [ ] **Step 7: Final commit (verification log)**

```bash
git commit --allow-empty -m "chore: phase 0+1 definition of done verified"
git tag phase-0-1-complete
```

---

## Spec coverage self-review

| Spec section | Implementing task(s) |
|---|---|
| §1 Goals / non-goals | informs all tasks; non-goals enforced by task 16 mock-backed pages |
| §2 Architecture & topology | tasks 1, 2, 11 |
| §3.1 common crate | tasks 4–7 |
| §3.2 auth-service | task 8 |
| §3.3 user-service | task 9 |
| §3.4 content-service | task 10 |
| §3.5 Envoy gateway | task 2 + task 11 verify |
| §3.6 Frontend | tasks 12–17 |
| §4 Data model & migrations | task 3 |
| §4.6 Kafka topics upfront | task 2 (init-topics) + task 3 verify |
| §4.7 Seed Phase 1 | task 18 |
| §5.1 Kafka event envelope | task 7 (events.rs), tasks 9 & 10 produce |
| §5.2 Redis keys | tasks 7 (rate limit), 8 (refresh sessions) |
| §5.3 Error envelope | task 4 (error.rs) |
| §5.4 Security (argon2, JWT, cookies) | task 6 |
| §5.5 Rate limits | task 7 (Redis) + task 2 (Envoy local_ratelimit) |
| §5.6 Observability | task 2 (prom/grafana), task 7 (tracing init) |
| §6 Testing & DoD | tasks 8, 9, 10, 17 + final task 20 |
| §7 Folder/file inventory | matches tasks 1–19 |
| §10 Decisions log | embodied across all tasks |

No spec section is left without a task.

## Placeholder self-scan

Searched the plan for TBD / TODO / "implement later" / "appropriate error handling" / "similar to task N": none present.

## Type consistency self-scan

- `AppError` variants are defined in task 4 and used identically in tasks 7–10.
- `Producer.produce_json` signature defined in task 5 and called identically in tasks 9, 10.
- `AppState` per service follows the same `{ db, redis, kafka?, cfg }` shape.
- `apiFetch<T>(fetch, path, init?)` defined in task 13 and used identically in tasks 14, 15, 17.
- Cookie names (`oec_access`, `oec_refresh`) match across tasks 6, 8, 13.
- Topic names (`oecophylla.content.created`, `oecophylla.user.followed`) match across tasks 2, 7, 9, 10.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-foundation-identity-content-plan.md`.**
