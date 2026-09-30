use std::net::SocketAddr;

use axum::{
    middleware::{from_fn, from_fn_with_state},
    routing::{get, post},
    Router,
};
use common::{
    config::SharedConfig,
    db::pg_pool,
    kafka::Producer,
    middleware::trace::init_tracing,
};

mod auth;
mod config;
mod cursor;
mod handlers;
mod repo;
mod state;
mod types;

use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("moderation-service");
    common::metrics::init_metrics();
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("MODERATION_BIND").unwrap_or_else(|_| "0.0.0.0:8006".into());

    let db = pg_pool(&cfg.database_url, 5).await?;
    let mod_cfg = config::ModerationConfig::from_env();
    let kafka = Producer::new(&mod_cfg.kafka_brokers)?;

    let state = AppState::new(db, cfg.clone(), mod_cfg, kafka);
    let auth_state = auth::AdminAuthState {
        db: state.db.clone(),
        jwt_secret: cfg.jwt_secret.as_bytes().to_vec(),
    };

    let admin_routes = Router::new()
        .route("/admin/reports", get(handlers::list_reports))
        .route("/admin/reports/{id}", get(handlers::get_report))
        .route("/admin/reports/{id}/resolve", post(handlers::resolve_report))
        .route("/admin/audit-logs", get(handlers::list_audit_logs))
        .route("/admin/users/{id}/history", get(handlers::user_history))
        .route("/admin/metrics", get(handlers::admin_metrics))
        .layer(from_fn_with_state(auth_state, auth::require_current_admin));

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(common::metrics::metrics_handler))
        .merge(admin_routes)
        .layer(from_fn(common::middleware::metrics_layer::track_metrics))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "moderation-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
