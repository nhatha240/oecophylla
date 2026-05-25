FROM rust:1-bookworm

RUN cargo install cargo-watch --locked \
 && cargo install sqlx-cli --no-default-features --features rustls,postgres --locked

WORKDIR /app

EXPOSE 3000

CMD ["cargo", "watch", "-q", "-c", "-w", "src", "-w", "Cargo.toml", "-w", "migrations", "-x", "run"]
