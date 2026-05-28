use common::{config::SharedConfig, kafka::Producer};
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;
use std::sync::Arc;

use crate::comment_fanout::CommentFanout;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    #[allow(dead_code)]
    pub redis: RedisPool,
    pub kafka: Producer,
    pub cfg: Arc<SharedConfig>,
    pub comment_fanout: Arc<CommentFanout>,
}
