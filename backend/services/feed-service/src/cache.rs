use anyhow::Context;
use deadpool_redis::Pool as RedisPool;
use deadpool_redis::redis::AsyncCommands;
use uuid::Uuid;

use crate::types::CachedFeed;

pub fn feed_key(user_id: Uuid) -> String {
    format!("feed:{user_id}")
}

pub const TRENDING_24H_KEY: &str = "trending:24h";

pub async fn get_cached_feed(
    redis: &RedisPool,
    user_id: Uuid,
) -> anyhow::Result<Option<CachedFeed>> {
    let mut conn = redis.get().await.context("redis get conn")?;
    let raw: Option<String> = conn
        .get(feed_key(user_id))
        .await
        .context("redis GET feed")?;
    match raw {
        Some(s) => {
            let feed = serde_json::from_str::<CachedFeed>(&s).context("decode CachedFeed")?;
            Ok(Some(feed))
        }
        None => Ok(None),
    }
}

pub async fn set_cached_feed(
    redis: &RedisPool,
    user_id: Uuid,
    feed: &CachedFeed,
    ttl_seconds: usize,
) -> anyhow::Result<()> {
    let mut conn = redis.get().await.context("redis get conn")?;
    let payload = serde_json::to_string(feed).context("encode CachedFeed")?;
    let _: () = conn
        .set_ex(feed_key(user_id), payload, ttl_seconds as u64)
        .await
        .context("redis SETEX feed")?;
    Ok(())
}

/// Top trending post IDs from the worker-maintained sorted set. Returns an
/// empty Vec when the set is missing — callers must handle that.
pub async fn trending_ids(redis: &RedisPool, limit: usize) -> anyhow::Result<Vec<Uuid>> {
    let mut conn = redis.get().await.context("redis get conn")?;
    let raw: Vec<String> = conn
        .zrevrange(TRENDING_24H_KEY, 0, (limit as isize).saturating_sub(1))
        .await
        .context("redis ZREVRANGE trending")?;
    let mut out = Vec::with_capacity(raw.len());
    for s in raw {
        if let Ok(uuid) = Uuid::parse_str(&s) {
            out.push(uuid);
        }
    }
    Ok(out)
}
