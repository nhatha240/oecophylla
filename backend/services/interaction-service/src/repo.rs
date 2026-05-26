use common::{error::AppError, ids::new_id, models::AuthUser};
use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::{Postgres, Transaction};
use uuid::Uuid;

// === interactions ===

pub async fn insert_interaction(
    tx: &mut Transaction<'_, Postgres>,
    user_id: Uuid, post_id: Uuid, type_: &str, weight: f32,
) -> Result<bool, AppError> {
    let r = sqlx::query(
        "INSERT INTO interactions (user_id, post_id, type, weight)
         VALUES ($1, $2, $3::interaction_type, $4)
         ON CONFLICT (user_id, post_id, type) DO NOTHING"
    ).bind(user_id).bind(post_id).bind(type_).bind(weight)
     .execute(&mut **tx).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn delete_interaction(
    tx: &mut Transaction<'_, Postgres>,
    user_id: Uuid, post_id: Uuid, type_: &str,
) -> Result<bool, AppError> {
    let r = sqlx::query(
        "DELETE FROM interactions WHERE user_id=$1 AND post_id=$2 AND type=$3::interaction_type"
    ).bind(user_id).bind(post_id).bind(type_).execute(&mut **tx).await?;
    Ok(r.rows_affected() == 1)
}

pub async fn bump_counter(
    tx: &mut Transaction<'_, Postgres>,
    post_id: Uuid, column: &str, delta: i32,
) -> Result<(), AppError> {
    // `column` is from a closed enum {"like_count","save_count","share_count","comment_count"}
    // so it is safe to interpolate into the SQL string.
    let sql = format!("UPDATE posts SET {column} = {column} + $1 WHERE id=$2");
    sqlx::query(&sql).bind(delta).bind(post_id).execute(&mut **tx).await?;
    Ok(())
}

pub async fn post_author(db: &sqlx::PgPool, post_id: Uuid) -> Result<Option<Uuid>, AppError> {
    Ok(sqlx::query_scalar::<_, Uuid>("SELECT author_id FROM posts WHERE id=$1")
        .bind(post_id).fetch_optional(db).await?)
}

// === reports ===

#[derive(Serialize, sqlx::FromRow)]
pub struct ReportRow { pub id: Uuid, pub status: String, pub created_at: DateTime<Utc> }

pub async fn insert_report(
    tx: &mut Transaction<'_, Postgres>,
    reporter_id: Uuid, post_id: Uuid, reason: &str, detail: Option<&str>,
) -> Result<Uuid, AppError> {
    let id: Uuid = sqlx::query_scalar(
        "INSERT INTO reports (reporter_id, post_id, reason, detail)
         VALUES ($1, $2, $3, $4) RETURNING id"
    ).bind(reporter_id).bind(post_id).bind(reason).bind(detail)
     .fetch_one(&mut **tx).await
     .map_err(|e| match e {
         sqlx::Error::Database(d) if d.code().as_deref() == Some("23505") =>
             AppError::Conflict { kind: "report".into() },
         o => AppError::Db(o),
     })?;
    Ok(id)
}

// === comments ===

#[derive(Serialize, sqlx::FromRow, Clone)]
pub struct CommentRow {
    pub id: Uuid,
    pub post_id: Uuid,
    pub author_id: Uuid,
    pub author_username: String,
    pub author_display_name: Option<String>,
    pub parent_comment_id: Option<Uuid>,
    pub content: String,
    pub is_deleted: bool,
    pub created_at: DateTime<Utc>,
    pub reply_count: i64,
}

pub async fn insert_comment(
    tx: &mut Transaction<'_, Postgres>,
    post_id: Uuid, author_id: Uuid, parent_comment_id: Option<Uuid>, content: &str,
) -> Result<Uuid, AppError> {
    // 1-level enforcement: if parent_comment_id is set, ensure parent is top-level (its parent_comment_id IS NULL).
    if let Some(p) = parent_comment_id {
        let parent_of_parent: Option<Option<Uuid>> = sqlx::query_scalar(
            "SELECT parent_comment_id FROM comments WHERE id=$1 AND post_id=$2"
        ).bind(p).bind(post_id).fetch_optional(&mut **tx).await?;
        match parent_of_parent {
            None => return Err(AppError::NotFound { kind: "parent_comment".into() }),
            Some(Some(_)) => return Err(AppError::Validation {
                field: "parent_comment_id".into(),
                message: "cannot reply more than one level deep".into(),
            }),
            Some(None) => { /* OK */ }
        }
    }
    let id = new_id();
    sqlx::query(
        "INSERT INTO comments (id, post_id, author_id, parent_comment_id, content)
         VALUES ($1, $2, $3, $4, $5)"
    ).bind(id).bind(post_id).bind(author_id).bind(parent_comment_id).bind(content)
     .execute(&mut **tx).await?;
    Ok(id)
}

pub async fn list_top_level_comments(
    db: &sqlx::PgPool, post_id: Uuid, limit: i64,
) -> Result<Vec<CommentRow>, AppError> {
    Ok(sqlx::query_as::<_, CommentRow>(
        "SELECT c.id, c.post_id, c.author_id,
                u.username AS author_username, u.display_name AS author_display_name,
                c.parent_comment_id,
                CASE WHEN c.is_deleted THEN '[đã xóa]' ELSE c.content END AS content,
                c.is_deleted, c.created_at,
                (SELECT count(*) FROM comments r
                  WHERE r.parent_comment_id = c.id AND r.is_deleted = false) AS reply_count
         FROM comments c
         JOIN users u ON u.id = c.author_id
         WHERE c.post_id = $1 AND c.parent_comment_id IS NULL AND c.is_deleted = false
         ORDER BY c.created_at ASC
         LIMIT $2"
    ).bind(post_id).bind(limit).fetch_all(db).await?)
}

pub async fn list_replies(
    db: &sqlx::PgPool, parent_id: Uuid, limit: i64,
) -> Result<Vec<CommentRow>, AppError> {
    Ok(sqlx::query_as::<_, CommentRow>(
        "SELECT c.id, c.post_id, c.author_id,
                u.username AS author_username, u.display_name AS author_display_name,
                c.parent_comment_id,
                CASE WHEN c.is_deleted THEN '[đã xóa]' ELSE c.content END AS content,
                c.is_deleted, c.created_at,
                0::bigint AS reply_count
         FROM comments c
         JOIN users u ON u.id = c.author_id
         WHERE c.parent_comment_id = $1 AND c.is_deleted = false
         ORDER BY c.created_at ASC
         LIMIT $2"
    ).bind(parent_id).bind(limit).fetch_all(db).await?)
}

pub async fn soft_delete_comment(
    tx: &mut Transaction<'_, Postgres>, id: Uuid, requester: AuthUser,
) -> Result<(Uuid /*post_id*/, bool /*was_top_level*/), AppError> {
    use common::models::UserRole;
    let row: Option<(Uuid, Uuid, Option<Uuid>, bool)> = sqlx::query_as(
        "SELECT post_id, author_id, parent_comment_id, is_deleted FROM comments WHERE id=$1"
    ).bind(id).fetch_optional(&mut **tx).await?;
    let (post_id, author_id, parent, already) = row.ok_or(AppError::NotFound { kind: "comment".into() })?;
    if already { return Ok((post_id, parent.is_none())); }
    if author_id != requester.id && requester.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    sqlx::query("UPDATE comments SET is_deleted = true WHERE id=$1")
        .bind(id).execute(&mut **tx).await?;
    Ok((post_id, parent.is_none()))
}

// === my-interactions ===

#[derive(Serialize)]
pub struct MyInteractions {
    pub liked: bool, pub saved: bool, pub shared: bool, pub hidden: bool, pub reported_pending: bool,
}

pub async fn my_interactions(
    db: &sqlx::PgPool, user_id: Uuid, post_id: Uuid,
) -> Result<MyInteractions, AppError> {
    let row: (Option<bool>, Option<bool>, Option<bool>, Option<bool>, bool) = sqlx::query_as(
        "SELECT
           bool_or(type = 'like'::interaction_type)  AS liked,
           bool_or(type = 'save'::interaction_type)  AS saved,
           bool_or(type = 'share'::interaction_type) AS shared,
           bool_or(type = 'hide'::interaction_type)  AS hidden,
           EXISTS (SELECT 1 FROM reports WHERE reporter_id=$1 AND post_id=$2 AND status='pending') AS reported_pending
         FROM interactions WHERE user_id=$1 AND post_id=$2"
    ).bind(user_id).bind(post_id).fetch_one(db).await?;
    Ok(MyInteractions {
        liked: row.0.unwrap_or(false), saved: row.1.unwrap_or(false),
        shared: row.2.unwrap_or(false), hidden: row.3.unwrap_or(false),
        reported_pending: row.4,
    })
}
