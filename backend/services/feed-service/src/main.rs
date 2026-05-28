use std::{net::SocketAddr, sync::Arc, time::Duration};

use axum::{
    middleware::{from_fn, from_fn_with_state},
    routing::get,
    Router,
};
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

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("feed-service");
    common::metrics::init_metrics();
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

    let trending_sse = Router::new()
        .route("/api/v1/feed/trending/stream", get(handlers::trending_stream));

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(common::metrics::metrics_handler))
        .merge(trending_sse)
        .merge(feed_routes)
        .layer(from_fn(common::middleware::metrics_layer::track_metrics))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "feed-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}

