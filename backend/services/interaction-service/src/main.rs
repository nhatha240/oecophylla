use axum::{
    Router,
    middleware::{from_fn, from_fn_with_state},
    routing::{delete, get, post},
};
use common::{
    config::SharedConfig,
    db::pg_pool,
    kafka::Producer,
    middleware::{
        rate_limit::{RateLimitPolicy, RateLimitState, enforce_rate_limit},
        trace::init_tracing,
    },
    redis::redis_pool,
};
use std::{net::SocketAddr, sync::Arc};

mod comment_dto;
mod comment_fanout;
mod events;
mod handlers;
mod repo;
mod state;

use comment_fanout::CommentFanout;
use state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing("interaction-service");
    common::metrics::init_metrics();
    let mut cfg = SharedConfig::from_env()?;
    cfg.bind = std::env::var("INTERACTION_BIND").unwrap_or_else(|_| "0.0.0.0:8004".into());

    let db = pg_pool(&cfg.database_url, 10).await?;
    let redis = redis_pool(&cfg.redis_url)?;
    let kafka = Producer::new(&cfg.kafka_brokers)?;
    let jwt_secret = Arc::new(cfg.jwt_secret.as_bytes().to_vec());
    let state = AppState {
        db,
        redis: redis.clone(),
        kafka,
        cfg: Arc::new(cfg.clone()),
        comment_fanout: Arc::new(CommentFanout::new()),
        behavior_view_counter_enabled: env_flag("BEHAVIOR_VIEW_COUNTER_ENABLED", false),
        positive_dwell_ms: std::env::var("POSITIVE_DWELL_MS")
            .ok()
            .and_then(|value| value.parse().ok())
            .filter(|value| (5_000..=1_800_000).contains(value))
            .unwrap_or(10_000),
    };

    let rl = |key_prefix: &'static str, max: u32| RateLimitState {
        redis: redis.clone(),
        policy: RateLimitPolicy::new(key_prefix, max),
        jwt_secret: jwt_secret.clone(),
    };

    let saved = Router::new()
        .route("/api/v1/posts/saved", get(handlers::list_saved_posts))
        .layer(from_fn_with_state(
            rl("saved_posts", 60),
            enforce_rate_limit,
        ));

    let toggles = Router::new()
        .route(
            "/api/v1/posts/{id}/like",
            post(handlers::like_post).delete(handlers::unlike_post),
        )
        .route(
            "/api/v1/posts/{id}/save",
            post(handlers::save_post).delete(handlers::unsave_post),
        )
        .route(
            "/api/v1/posts/{id}/share",
            post(handlers::share_post).delete(handlers::unshare_post),
        )
        .route(
            "/api/v1/posts/{id}/hide",
            post(handlers::hide_post).delete(handlers::unhide_post),
        )
        .layer(from_fn_with_state(
            rl("interactions_toggle", 120),
            enforce_rate_limit,
        ));

    let report = Router::new()
        .route("/api/v1/posts/{id}/report", post(handlers::report_post))
        .layer(from_fn_with_state(rl("report", 10), enforce_rate_limit));

    let comments = Router::new()
        .route(
            "/api/v1/posts/{id}/comments",
            get(handlers::list_comments).post(handlers::create_comment),
        )
        .route(
            "/api/v1/posts/{id}/comments/stream",
            get(handlers::comments_sse_stream),
        )
        .route(
            "/api/v1/comments/{id}/replies",
            get(handlers::list_comment_replies),
        )
        .route("/api/v1/comments/{id}", delete(handlers::delete_comment))
        .layer(from_fn_with_state(rl("comments", 20), enforce_rate_limit));

    let me_routes = Router::new()
        .route("/api/v1/posts/{id}/me", get(handlers::my_post_interactions))
        .route("/api/v1/interactions/me/batch", post(handlers::batch_me))
        .layer(from_fn_with_state(
            rl("interactions_me", 200),
            enforce_rate_limit,
        ));

    let behavior_events = Router::new()
        .route(
            "/api/v1/interactions/events/batch",
            post(handlers::ingest_behavior_events),
        )
        .layer(from_fn_with_state(
            rl("behavior_events", 600),
            enforce_rate_limit,
        ));

    let mut app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/metrics", get(common::metrics::metrics_handler))
        .merge(saved)
        .merge(toggles)
        .merge(report)
        .merge(comments)
        .merge(me_routes);
    if env_flag("BEHAVIOR_EVENTS_ENABLED", true) {
        app = app.merge(behavior_events);
    }
    let app = app
        .layer(from_fn(common::middleware::metrics_layer::track_metrics))
        .with_state(state);

    let addr: SocketAddr = cfg.bind.parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "interaction-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}

fn env_flag(key: &str, default: bool) -> bool {
    std::env::var(key)
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(default)
}
