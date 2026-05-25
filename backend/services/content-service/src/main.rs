use axum::{routing::get, Router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let addr: SocketAddr = "0.0.0.0:8003".parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "listening");
    axum::serve(listener, app).await?;
    Ok(())
}
