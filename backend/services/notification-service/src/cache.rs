use deadpool_redis::Pool as RedisPool;
use redis::AsyncCommands;
use uuid::Uuid;

const UNREAD_TTL_SECONDS: usize = 1800;

fn unread_key(user_id: Uuid) -> String {
    format!("notif:unread_count:{user_id}")
}

/// Read the cached unread count. Returns `Ok(None)` on a cache miss.
pub async fn unread_count(redis: &RedisPool, user_id: Uuid) -> anyhow::Result<Option<i64>> {
    let mut conn = redis.get().await?;
    let val: Option<i64> = conn.get(unread_key(user_id)).await?;
    Ok(val)
}

/// Write (or refresh) the cached unread count with a fixed TTL.
pub async fn set_unread_count(redis: &RedisPool, user_id: Uuid, count: i64) -> anyhow::Result<()> {
    let mut conn = redis.get().await?;
    let _: () = conn
        .set_ex(unread_key(user_id), count, UNREAD_TTL_SECONDS as u64)
        .await?;
    Ok(())
}

/// Delete the cached unread count so the next read falls through to the DB.
pub async fn invalidate_unread_count(redis: &RedisPool, user_id: Uuid) -> anyhow::Result<()> {
    let mut conn = redis.get().await?;
    conn.del::<_, i64>(unread_key(user_id)).await?;
    Ok(())
}
