use axum::{routing::get, Router};
use std::net::SocketAddr;

mod events;
mod handlers;
mod repo;
mod state;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    common::middleware::trace::init_tracing("interaction-service");
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let addr: SocketAddr = std::env::var("INTERACTION_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8004".into()).parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "interaction-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
