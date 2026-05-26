#[tokio::main]
async fn main() -> anyhow::Result<()> {
    common::middleware::trace::init_tracing("cache-invalidator");
    tracing::info!("cache-invalidator started");
    tokio::signal::ctrl_c().await?;
    tracing::info!("cache-invalidator shutting down");
    Ok(())
}
