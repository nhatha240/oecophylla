# syntax=docker/dockerfile:1.7
FROM rust:1.85 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
COPY . .
RUN cargo build --release -p content-service

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/content-service /usr/local/bin/content-service
EXPOSE 8003
ENTRYPOINT ["/usr/local/bin/content-service"]
