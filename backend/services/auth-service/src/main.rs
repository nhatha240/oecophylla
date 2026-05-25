use axum::{Router, routing::{post, delete, get}};
use common::{config::SharedConfig, db::pg_pool, redis::redis_pool, middleware::trace::init_tracing};
use std::{net::SocketAddr, sync::Arc};

mod state; mod handlers; mod repo;
use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("auth-service");
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("AUTH_BIND").unwrap_or_else(|_| "0.0.0.0:8001".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let state = AppState { db, redis, cfg: Arc::new(cfg.clone()) };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/api/v1/auth/register", post(handlers::register))
        .route("/api/v1/auth/login",    post(handlers::login))
        .route("/api/v1/auth/refresh",  post(handlers::refresh))
        .route("/api/v1/auth/logout",   delete(handlers::logout))
        .route("/api/v1/auth/me",       get(handlers::me))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "auth-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
