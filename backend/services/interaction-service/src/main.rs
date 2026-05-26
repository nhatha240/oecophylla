use axum::{
    Router,
    routing::{delete, get, post},
};
use common::{
    config::SharedConfig,
    db::pg_pool,
    kafka::Producer,
    middleware::trace::init_tracing,
    redis::redis_pool,
};
use std::{net::SocketAddr, sync::Arc};

mod events;
mod handlers;
mod repo;
mod state;

use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("interaction-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("INTERACTION_BIND").unwrap_or_else(|_| "0.0.0.0:8004".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let state = AppState { db, redis, kafka, cfg: Arc::new(cfg.clone()) };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route(
            "/api/v1/posts/:id/like",
            post(handlers::like_post).delete(handlers::unlike_post),
        )
        .route(
            "/api/v1/posts/:id/save",
            post(handlers::save_post).delete(handlers::unsave_post),
        )
        .route(
            "/api/v1/posts/:id/share",
            post(handlers::share_post).delete(handlers::unshare_post),
        )
        .route(
            "/api/v1/posts/:id/hide",
            post(handlers::hide_post).delete(handlers::unhide_post),
        )
        .route("/api/v1/posts/:id/report", post(handlers::report_post))
        .route(
            "/api/v1/posts/:id/comments",
            get(handlers::list_comments).post(handlers::create_comment),
        )
        .route("/api/v1/posts/:id/me", get(handlers::my_post_interactions))
        .route(
            "/api/v1/comments/:id/replies",
            get(handlers::list_comment_replies),
        )
        .route("/api/v1/comments/:id", delete(handlers::delete_comment))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "interaction-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
