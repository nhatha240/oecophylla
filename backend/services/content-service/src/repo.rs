use chrono::{DateTime, Utc};
use common::{error::AppError, ids::new_id, models::PostStatus};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, serde::Serialize, Clone)]
pub struct PostRow {
    pub id: Uuid,
    pub author_id: Uuid,
    pub content: String,
    pub media_urls: Vec<String>,
    pub tags: Vec<String>,
    pub topics: Vec<String>,
    pub safety_score: f32,
    pub status: PostStatus,
    pub view_count: i64,
    pub like_count: i32,
    pub comment_count: i32,
    pub save_count: i32,
    pub share_count: i32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

pub async fn insert(
    db: &PgPool,
    author: Uuid,
    content: &str,
    media: &[String],
    tags: &[String],
    status: PostStatus,
) -> Result<PostRow, AppError> {
    let id = new_id();
    Ok(sqlx::query_as::<_, PostRow>(
        "INSERT INTO posts (id, author_id, content, media_urls, tags, status)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, like_count, comment_count, save_count, share_count, created_at, updated_at",
    )
    .bind(id)
    .bind(author)
    .bind(content)
    .bind(media)
    .bind(tags)
    .bind(status)
    .fetch_one(db)
    .await?)
}

pub async fn by_id(db: &PgPool, id: Uuid) -> Result<Option<PostRow>, AppError> {
    Ok(sqlx::query_as::<_, PostRow>(
        "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, like_count, comment_count, save_count, share_count, created_at, updated_at
         FROM posts WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(db)
    .await?)
}

pub async fn list_by_author(
    db: &PgPool,
    author: Uuid,
    limit: i64,
) -> Result<Vec<PostRow>, AppError> {
    Ok(sqlx::query_as::<_, PostRow>(
        "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, like_count, comment_count, save_count, share_count, created_at, updated_at
         FROM posts WHERE author_id = $1 AND status = 'published'
         ORDER BY created_at DESC LIMIT $2",
    )
    .bind(author)
    .bind(limit)
    .fetch_all(db)
    .await?)
}

pub async fn delete(db: &PgPool, id: Uuid) -> Result<bool, AppError> {
    Ok(sqlx::query("DELETE FROM posts WHERE id = $1")
        .bind(id)
        .execute(db)
        .await?
        .rows_affected()
        == 1)
}

pub async fn increment_view(db: &PgPool, id: Uuid) -> Result<(), AppError> {
    sqlx::query("UPDATE posts SET view_count = view_count + 1 WHERE id = $1")
        .bind(id)
        .execute(db)
        .await?;
    Ok(())
}
