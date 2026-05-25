use common::{config::SharedConfig, kafka::Producer};
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;
use std::sync::Arc;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub kafka: Producer,
    pub cfg: Arc<SharedConfig>,
}
