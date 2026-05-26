use common::{config::SharedConfig, middleware::trace::init_tracing, redis::redis_pool};

mod consumer;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("cache-invalidator");
    let cfg = SharedConfig::from_env()?;
    let redis = redis_pool(&cfg.redis_url)?;
    tracing::info!("cache-invalidator started");

    tokio::select! {
        res = consumer::run(cfg.kafka_brokers.clone(), redis) => {
            if let Err(err) = res {
                tracing::error!(error = %err, "consumer loop exited");
            }
        }
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("cache-invalidator shutting down on SIGINT");
        }
    }

    Ok(())
}
