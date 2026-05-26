use std::sync::Arc;

use common::config::SharedConfig;
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;

#[derive(Clone, Debug)]
pub struct FeedConfig {
    pub recommendation_url: String,
    pub recommendation_timeout_ms: u64,
    pub feed_cache_ttl_seconds: usize,
    pub feed_result_size: usize,
    pub feed_candidate_pool: usize,
}

impl FeedConfig {
    pub fn from_env() -> Self {
        Self {
            recommendation_url: std::env::var("RECOMMENDATION_SERVICE_URL")
                .unwrap_or_else(|_| "http://recommendation-api:8090".into()),
            recommendation_timeout_ms: std::env::var("FEED_RECOMMENDATION_TIMEOUT_MS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(500),
            feed_cache_ttl_seconds: std::env::var("FEED_CACHE_TTL_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(600),
            feed_result_size: std::env::var("FEED_RESULT_SIZE")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(50),
            feed_candidate_pool: std::env::var("FEED_CANDIDATE_POOL_SIZE")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(300),
        }
    }
}

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub http: reqwest::Client,
    pub cfg: Arc<SharedConfig>,
    pub feed_cfg: Arc<FeedConfig>,
}
