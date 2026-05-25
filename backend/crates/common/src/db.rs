use sqlx::{postgres::PgPoolOptions, PgPool};
use std::time::Duration;

pub async fn pg_pool(url: &str, max_conn: u32) -> anyhow::Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_conn)
        .acquire_timeout(Duration::from_secs(5))
        .connect(url)
        .await?;
    Ok(pool)
}
