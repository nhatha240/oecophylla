use std::{net::SocketAddr, sync::Arc, time::Duration};

use axum::{middleware::from_fn_with_state, routing::get, Router};
use common::{
    config::SharedConfig,
    db::pg_pool,
    middleware::{
        rate_limit::{enforce_rate_limit, RateLimitPolicy, RateLimitState},
        trace::init_tracing,
    },
    redis::redis_pool,
};

mod cache;
mod handlers;
mod recommendation;
mod repo;
mod state;
mod types;

use state::{AppState, FeedConfig};

async fn metrics_stub() -> &'static str {
    // Phase 2B ships only a placeholder; real exporter is part of Phase 4.
    "# feed-service metrics not yet implemented\n"
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("feed-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("FEED_BIND").unwrap_or_else(|_| "0.0.0.0:8005".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let http = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()?;

    let feed_cfg = Arc::new(FeedConfig::from_env());
    let jwt_secret = Arc::new(cfg.jwt_secret.as_bytes().to_vec());

    let state = AppState {
        db,
        redis: redis.clone(),
        http,
        cfg: Arc::new(cfg.clone()),
        feed_cfg: feed_cfg.clone(),
    };

    let rl_feed = RateLimitState {
        redis: redis.clone(),
        policy: RateLimitPolicy::new("feed", 120),
        jwt_secret,
    };

    let feed_routes = Router::new()
        .route("/api/v1/feed", get(handlers::get_feed))
        .layer(from_fn_with_state(rl_feed, enforce_rate_limit));

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(metrics_stub))
        .merge(feed_routes)
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "feed-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}

