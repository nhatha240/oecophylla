use std::sync::Arc;

use common::{config::SharedConfig, kafka::Producer};
use sqlx::PgPool;

use crate::config::ModerationConfig;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub cfg: Arc<SharedConfig>,
    pub mod_cfg: Arc<ModerationConfig>,
    pub kafka: Producer,
}

impl AppState {
    pub fn new(
        db: PgPool,
        cfg: SharedConfig,
        mod_cfg: ModerationConfig,
        kafka: Producer,
    ) -> Self {
        Self {
            db,
            cfg: Arc::new(cfg),
            mod_cfg: Arc::new(mod_cfg),
            kafka,
        }
    }
}
