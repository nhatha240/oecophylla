FROM rust:1.94.0-trixie AS builder
RUN cargo install sqlx-cli --version '0.8.6' --locked --no-default-features --features postgres,rustls

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder --chown=10001:10001 --chmod=0555 /usr/local/cargo/bin/sqlx /usr/local/bin/sqlx
COPY --chown=10001:10001 . /app/migrations
USER 10001:10001
ENTRYPOINT ["/usr/local/bin/sqlx"]
