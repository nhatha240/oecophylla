use std::{net::SocketAddr, sync::Arc};

use axum::{
    middleware::from_fn_with_state,
    routing::{get, post},
    Router,
};
use common::{
    config::SharedConfig,
    db::pg_pool,
    middleware::{
        auth::{require_auth, AuthState},
        trace::init_tracing,
    },
    redis::redis_pool,
};

mod cache;
mod config;
mod cursor;
mod fanout;
mod handlers;
mod kafka;
mod repo;
mod state;
mod types;

use state::AppState;

async fn metrics_stub() -> &'static str {
    "# notification-service metrics not yet implemented\n"
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("notification-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("NOTIFICATION_BIND").unwrap_or_else(|_| "0.0.0.0:8007".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let notif_cfg = config::NotificationConfig::from_env();

    let state = AppState::new(db, redis, cfg.clone(), notif_cfg);

    // Spawn Kafka consumers in background (best-effort; main HTTP server keeps running).
    kafka::spawn_consumers(state.clone());

    let jwt_secret = Arc::new(cfg.jwt_secret.as_bytes().to_vec());
    let auth_state = AuthState { jwt_secret };

    // All /api/v1/notifications routes require a valid JWT cookie.
    let notif_routes = Router::new()
        .route("/api/v1/notifications", get(handlers::list_notifications))
        .route(
            "/api/v1/notifications/unread-count",
            get(handlers::unread_count),
        )
        .route(
            "/api/v1/notifications/read-all",
            post(handlers::mark_all_read),
        )
        .route("/api/v1/notifications/:id/read", post(handlers::mark_read))
        .route("/api/v1/notifications/stream", get(handlers::sse_stream))
        .layer(from_fn_with_state(auth_state, require_auth));

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(metrics_stub))
        .merge(notif_routes)
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "notification-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
