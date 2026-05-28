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
    topics: &[String],
    status: PostStatus,
) -> Result<PostRow, AppError> {
    let id = new_id();
    Ok(sqlx::query_as::<_, PostRow>(
        "INSERT INTO posts (id, author_id, content, media_urls, tags, topics, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING id, author_id, content, media_urls, tags, topics, safety_score, status, view_count, like_count, comment_count, save_count, share_count, created_at, updated_at",
    )
    .bind(id)
    .bind(author)
    .bind(content)
    .bind(media)
    .bind(tags)
    .bind(topics)
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

pub async fn list_by_tag(
    db: &PgPool,
    tag: &str,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
) -> Result<Vec<PostRow>, AppError> {
    Ok(match cursor {
        Some((ts, id)) => {
            sqlx::query_as::<_, PostRow>(
                "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status,
                        view_count, like_count, comment_count, save_count, share_count,
                        created_at, updated_at
                 FROM posts
                 WHERE status = 'published'
                   AND tags @> ARRAY[$1]
                   AND (created_at, id) < ($2, $3)
                 ORDER BY created_at DESC
                 LIMIT $4",
            )
            .bind(tag)
            .bind(ts)
            .bind(id)
            .bind(limit)
            .fetch_all(db)
            .await?
        }
        None => {
            sqlx::query_as::<_, PostRow>(
                "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status,
                        view_count, like_count, comment_count, save_count, share_count,
                        created_at, updated_at
                 FROM posts
                 WHERE status = 'published'
                   AND tags @> ARRAY[$1]
                 ORDER BY created_at DESC
                 LIMIT $2",
            )
            .bind(tag)
            .bind(limit)
            .fetch_all(db)
            .await?
        }
    })
}

pub async fn list_by_topic(
    db: &PgPool,
    topic: &str,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
) -> Result<Vec<PostRow>, AppError> {
    Ok(match cursor {
        Some((ts, id)) => {
            sqlx::query_as::<_, PostRow>(
                "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status,
                        view_count, like_count, comment_count, save_count, share_count,
                        created_at, updated_at
                 FROM posts
                 WHERE status = 'published'
                   AND topics @> ARRAY[$1]
                   AND (created_at, id) < ($2, $3)
                 ORDER BY created_at DESC
                 LIMIT $4",
            )
            .bind(topic)
            .bind(ts)
            .bind(id)
            .bind(limit)
            .fetch_all(db)
            .await?
        }
        None => {
            sqlx::query_as::<_, PostRow>(
                "SELECT id, author_id, content, media_urls, tags, topics, safety_score, status,
                        view_count, like_count, comment_count, save_count, share_count,
                        created_at, updated_at
                 FROM posts
                 WHERE status = 'published'
                   AND topics @> ARRAY[$1]
                 ORDER BY created_at DESC
                 LIMIT $2",
            )
            .bind(topic)
            .bind(limit)
            .fetch_all(db)
            .await?
        }
    })
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

#[derive(serde::Serialize, sqlx::FromRow)]
pub struct SearchPostRow {
    pub id: Uuid,
    pub author_id: Uuid,
    pub content: String,
    pub tags: Vec<String>,
    pub topics: Vec<String>,
    pub status: PostStatus,
    pub view_count: i64,
    pub created_at: DateTime<Utc>,
    pub rank: f32,
}

pub async fn search_posts(
    db: &PgPool,
    query: &str,
    limit: i64,
    cursor_created_at: Option<DateTime<Utc>>,
    cursor_id: Option<Uuid>,
) -> Result<Vec<SearchPostRow>, AppError> {
    if cursor_created_at.is_some() && cursor_id.is_some() {
        Ok(sqlx::query_as::<_, SearchPostRow>(
            "SELECT id, author_id, content, tags, topics, status, view_count, created_at,
                    ts_rank(search_vector, plainto_tsquery('english', $1)) AS rank
             FROM posts
             WHERE search_vector @@ plainto_tsquery('english', $1)
               AND status = 'published'
               AND (created_at, id) < ($2, $3)
             ORDER BY rank DESC, created_at DESC
             LIMIT $4",
        )
        .bind(query)
        .bind(cursor_created_at.unwrap())
        .bind(cursor_id.unwrap())
        .bind(limit)
        .fetch_all(db)
        .await?)
    } else {
        Ok(sqlx::query_as::<_, SearchPostRow>(
            "SELECT id, author_id, content, tags, topics, status, view_count, created_at,
                    ts_rank(search_vector, plainto_tsquery('english', $1)) AS rank
             FROM posts
             WHERE search_vector @@ plainto_tsquery('english', $1)
               AND status = 'published'
             ORDER BY rank DESC, created_at DESC
             LIMIT $2",
        )
        .bind(query)
        .bind(limit)
        .fetch_all(db)
        .await?)
    }
}
