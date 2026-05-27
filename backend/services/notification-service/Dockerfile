# syntax=docker/dockerfile:1.7
FROM rust:1.85 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
COPY . .
RUN cargo build --release -p notification-service

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/notification-service /usr/local/bin/notification-service
EXPOSE 8007
ENTRYPOINT ["/usr/local/bin/notification-service"]
