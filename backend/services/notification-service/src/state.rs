use std::sync::Arc;

use common::config::SharedConfig;
use deadpool_redis::Pool as RedisPool;
use sqlx::PgPool;

use crate::{config::NotificationConfig, fanout::Fanout};

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: RedisPool,
    pub cfg: Arc<SharedConfig>,
    pub notif_cfg: Arc<NotificationConfig>,
    pub fanout: Arc<Fanout>,
}

impl AppState {
    pub fn new(
        db: PgPool,
        redis: RedisPool,
        cfg: SharedConfig,
        notif_cfg: NotificationConfig,
    ) -> Self {
        Self {
            db,
            redis,
            cfg: Arc::new(cfg),
            notif_cfg: Arc::new(notif_cfg),
            fanout: Arc::new(Fanout::new()),
        }
    }
}
