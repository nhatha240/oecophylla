# syntax=docker/dockerfile:1.7
FROM rust:1.85 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
COPY . .
RUN cargo build --release -p auth-service

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/auth-service /usr/local/bin/auth-service
EXPOSE 8001
ENTRYPOINT ["/usr/local/bin/auth-service"]
