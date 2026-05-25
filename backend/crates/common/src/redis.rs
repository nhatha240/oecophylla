use deadpool_redis::{Config, Runtime, Pool};

pub fn redis_pool(url: &str) -> anyhow::Result<Pool> {
    let cfg = Config::from_url(url);
    Ok(cfg.create_pool(Some(Runtime::Tokio1))?)
}
