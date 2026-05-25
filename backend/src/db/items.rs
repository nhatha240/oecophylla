use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, sqlx::FromRow)]
pub struct Item {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct ItemInput {
    pub name: String,
    pub description: Option<String>,
}

pub async fn list(pool: &PgPool) -> Result<Vec<Item>, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "SELECT id, name, description, created_at, updated_at \
         FROM items ORDER BY created_at DESC",
    )
    .fetch_all(pool)
    .await
}

pub async fn create(pool: &PgPool, input: &ItemInput) -> Result<Item, sqlx::Error> {
    let id = Uuid::now_v7();
    sqlx::query_as::<_, Item>(
        "INSERT INTO items (id, name, description) \
         VALUES ($1, $2, $3) \
         RETURNING id, name, description, created_at, updated_at",
    )
    .bind(id)
    .bind(&input.name)
    .bind(&input.description)
    .fetch_one(pool)
    .await
}

pub async fn get(pool: &PgPool, id: Uuid) -> Result<Item, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "SELECT id, name, description, created_at, updated_at \
         FROM items WHERE id = $1",
    )
    .bind(id)
    .fetch_one(pool)
    .await
}

pub async fn update(pool: &PgPool, id: Uuid, input: &ItemInput) -> Result<Item, sqlx::Error> {
    sqlx::query_as::<_, Item>(
        "UPDATE items \
         SET name = $2, description = $3, updated_at = now() \
         WHERE id = $1 \
         RETURNING id, name, description, created_at, updated_at",
    )
    .bind(id)
    .bind(&input.name)
    .bind(&input.description)
    .fetch_one(pool)
    .await
}

pub async fn delete(pool: &PgPool, id: Uuid) -> Result<(), sqlx::Error> {
    let result = sqlx::query("DELETE FROM items WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await?;

    if result.rows_affected() == 0 {
        return Err(sqlx::Error::RowNotFound);
    }
    Ok(())
}
