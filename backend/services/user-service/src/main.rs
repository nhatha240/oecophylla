use axum::{
    middleware::from_fn,
    routing::{get, post},
    Router,
};
use common::{
    config::SharedConfig, db::pg_pool, kafka::Producer, middleware::trace::init_tracing,
    redis::redis_pool,
};
use std::{net::SocketAddr, sync::Arc};

mod handlers;
mod repo;
mod state;

use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("user-service");
    common::metrics::init_metrics();
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("USER_BIND").unwrap_or_else(|_| "0.0.0.0:8002".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let state = AppState {
        db,
        redis,
        kafka,
        cfg: Arc::new(cfg.clone()),
    };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(common::metrics::metrics_handler))
        .route("/api/v1/users", get(handlers::search_users))
        .route("/api/v1/users/suggestions", get(handlers::suggestions))
        .route(
            "/api/v1/users/{id}",
            get(handlers::get).put(handlers::update),
        )
        .route(
            "/api/v1/users/{id}/follow",
            post(handlers::follow).delete(handlers::unfollow),
        )
        .route("/api/v1/users/{id}/followers", get(handlers::followers))
        .route("/api/v1/users/{id}/following", get(handlers::following))
        .layer(from_fn(common::middleware::metrics_layer::track_metrics))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "user-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
