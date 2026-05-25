use deadpool_redis::{Config, Pool, Runtime};

pub fn redis_pool(url: &str) -> anyhow::Result<Pool> {
    let cfg = Config::from_url(url);
    Ok(cfg.create_pool(Some(Runtime::Tokio1))?)
}
