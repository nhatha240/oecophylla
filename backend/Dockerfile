# syntax=docker/dockerfile:1.7

ARG RUST_VERSION=1.94.0
ARG DEBIAN_RELEASE=trixie

# Install build tooling once. Every service target below shares this stage.
FROM rust:${RUST_VERSION}-${DEBIAN_RELEASE} AS chef
ARG CARGO_CHEF_VERSION=0.1.78
WORKDIR /app

RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      cmake \
      pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && cargo install cargo-chef --version "${CARGO_CHEF_VERSION}" --locked

# Source changes may rerun prepare, but an unchanged recipe.json keeps the
# expensive shared-dependencies stage cacheable.
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# Cook the complete workspace once. Do not add --package here: this exact layer
# must be shared by every service target.
FROM chef AS shared-dependencies
ARG CARGO_DEPS_JOBS=8
COPY --from=planner /app/recipe.json recipe.json
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_DEPS_JOBS}" \
    cargo chef cook \
      --release \
      --locked \
      --recipe-path recipe.json

# Shared application source belongs here. A change to common correctly
# invalidates every service builder, while service-local changes are isolated by
# the per-builder COPY instructions below.
FROM shared-dependencies AS source
ARG CARGO_SERVICE_JOBS=4
COPY Cargo.toml Cargo.lock ./
COPY crates/common crates/common
COPY services/auth-service/Cargo.toml services/auth-service/Cargo.toml
COPY services/user-service/Cargo.toml services/user-service/Cargo.toml
COPY services/content-service/Cargo.toml services/content-service/Cargo.toml
COPY services/interaction-service/Cargo.toml services/interaction-service/Cargo.toml
COPY services/feed-service/Cargo.toml services/feed-service/Cargo.toml
COPY services/moderation-service/Cargo.toml services/moderation-service/Cargo.toml
COPY services/notification-service/Cargo.toml services/notification-service/Cargo.toml
COPY services/cache-invalidator/Cargo.toml services/cache-invalidator/Cargo.toml

FROM source AS auth-builder
COPY services/auth-service services/auth-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p auth-service \
    && install -Dm0555 target/release/auth-service /out/auth-service

FROM source AS user-builder
COPY services/user-service services/user-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p user-service \
    && install -Dm0555 target/release/user-service /out/user-service

FROM source AS content-builder
COPY services/content-service services/content-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p content-service \
    && install -Dm0555 target/release/content-service /out/content-service

FROM source AS interaction-builder
COPY services/interaction-service services/interaction-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p interaction-service \
    && install -Dm0555 target/release/interaction-service /out/interaction-service

FROM source AS feed-builder
COPY services/feed-service services/feed-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p feed-service \
    && install -Dm0555 target/release/feed-service /out/feed-service

FROM source AS moderation-builder
COPY services/moderation-service services/moderation-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p moderation-service \
    && install -Dm0555 target/release/moderation-service /out/moderation-service

FROM source AS notification-builder
COPY services/notification-service services/notification-service
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p notification-service \
    && install -Dm0555 target/release/notification-service /out/notification-service

FROM source AS cache-invalidator-builder
COPY services/cache-invalidator services/cache-invalidator
RUN --mount=type=cache,id=oecophylla-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=oecophylla-cargo-git,target=/usr/local/cargo/git \
    CARGO_BUILD_JOBS="${CARGO_SERVICE_JOBS}" cargo build --release --locked -p cache-invalidator \
    && install -Dm0555 target/release/cache-invalidator /out/cache-invalidator

# The runtime contains only glibc, the verified dynamic zlib dependency, CA
# roots, and a non-root account suitable for Docker Compose and Kubernetes.
FROM debian:${DEBIAN_RELEASE}-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd \
      --uid 10001 \
      --gid app \
      --no-create-home \
      --home-dir /nonexistent \
      --shell /usr/sbin/nologin \
      app
USER 10001:10001

FROM runtime AS auth-service
COPY --from=auth-builder --chown=10001:10001 --chmod=0555 /out/auth-service /usr/local/bin/auth-service
EXPOSE 8001
ENTRYPOINT ["/usr/local/bin/auth-service"]

FROM runtime AS user-service
COPY --from=user-builder --chown=10001:10001 --chmod=0555 /out/user-service /usr/local/bin/user-service
EXPOSE 8002
ENTRYPOINT ["/usr/local/bin/user-service"]

FROM runtime AS content-service
COPY --from=content-builder --chown=10001:10001 --chmod=0555 /out/content-service /usr/local/bin/content-service
EXPOSE 8003
ENTRYPOINT ["/usr/local/bin/content-service"]

FROM runtime AS interaction-service
COPY --from=interaction-builder --chown=10001:10001 --chmod=0555 /out/interaction-service /usr/local/bin/interaction-service
EXPOSE 8004
ENTRYPOINT ["/usr/local/bin/interaction-service"]

FROM runtime AS feed-service
COPY --from=feed-builder --chown=10001:10001 --chmod=0555 /out/feed-service /usr/local/bin/feed-service
EXPOSE 8005
ENTRYPOINT ["/usr/local/bin/feed-service"]

FROM runtime AS moderation-service
COPY --from=moderation-builder --chown=10001:10001 --chmod=0555 /out/moderation-service /usr/local/bin/moderation-service
EXPOSE 8006
ENTRYPOINT ["/usr/local/bin/moderation-service"]

FROM runtime AS notification-service
COPY --from=notification-builder --chown=10001:10001 --chmod=0555 /out/notification-service /usr/local/bin/notification-service
EXPOSE 8007
ENTRYPOINT ["/usr/local/bin/notification-service"]

FROM runtime AS cache-invalidator
COPY --from=cache-invalidator-builder --chown=10001:10001 --chmod=0555 /out/cache-invalidator /usr/local/bin/cache-invalidator
ENTRYPOINT ["/usr/local/bin/cache-invalidator"]
