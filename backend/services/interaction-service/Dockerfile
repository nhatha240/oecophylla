# syntax=docker/dockerfile:1.7

# ── Stage 1: install cargo-chef (layer cached after first build) ─────────────
FROM rust:1.94.0 AS chef
WORKDIR /app
ENV RUSTUP_TOOLCHAIN=1.94.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && cargo install cargo-chef --locked

# ── Stage 2: compute dependency recipe from workspace manifests ──────────────
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# ── Stage 3: build ALL workspace deps (cached when Cargo.toml/Cargo.lock unchanged) ──
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
RUN cargo build --release -p interaction-service

# ── Stage 4: minimal runtime image ───────────────────────────────────────────
FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/interaction-service /usr/local/bin/interaction-service
EXPOSE 8004
ENTRYPOINT ["/usr/local/bin/interaction-service"]
