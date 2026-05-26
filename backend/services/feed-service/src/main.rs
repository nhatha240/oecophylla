use axum::{routing::get, Router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    common::middleware::trace::init_tracing("feed-service");
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let addr: SocketAddr = std::env::var("FEED_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8005".into())
        .parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "feed-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
