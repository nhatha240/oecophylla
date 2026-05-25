use common::config::SharedConfig;
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;
use std::sync::Arc;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub cfg: Arc<SharedConfig>,
}
