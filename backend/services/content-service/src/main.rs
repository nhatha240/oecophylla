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

mod cursor;
mod handlers;
mod repo;
mod state;
mod update;

use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("content-service");
    common::metrics::init_metrics();
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("CONTENT_BIND").unwrap_or_else(|_| "0.0.0.0:8003".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let state = AppState {
        db,
        redis,
        kafka,
        cfg: Arc::new(cfg.clone()),
        legacy_view_counter_enabled: env_flag("LEGACY_VIEW_COUNTER_ENABLED", false),
    };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(common::metrics::metrics_handler))
        .route("/api/v1/posts", post(handlers::create).get(handlers::list))
        .route(
            "/api/v1/posts/{id}",
            get(handlers::get_one).delete(handlers::delete_post),
        )
        .route("/api/v1/posts/{id}/view", post(handlers::view))
        .route("/api/v1/search", get(handlers::search))
        .layer(from_fn(common::middleware::metrics_layer::track_metrics))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "content-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}

fn env_flag(key: &str, default: bool) -> bool {
    let value = std::env::var(key).ok();
    parse_flag(value.as_deref(), default)
}

fn parse_flag(value: Option<&str>, default: bool) -> bool {
    value
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::parse_flag;

    #[test]
    fn legacy_counter_defaults_to_disabled() {
        assert!(!parse_flag(None, false));
    }

    #[test]
    fn counter_flag_accepts_explicit_rollout_values() {
        for enabled in ["1", "true", "TRUE", "yes", "on"] {
            assert!(parse_flag(Some(enabled), false), "{enabled}");
        }
        for disabled in ["0", "false", "no", "off", "invalid"] {
            assert!(!parse_flag(Some(disabled), true), "{disabled}");
        }
    }
}
