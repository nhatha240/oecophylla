use anyhow::Context;
use chrono::{DateTime, Utc};
use sqlx::{postgres::PgRow, PgPool, Row};
use uuid::Uuid;

use crate::types::{ActorDto, NotificationDto, PostSnippet};

const SNIPPET_LEN: i32 = 100;

// ── Row → DTO mapping ─────────────────────────────────────────────────────────

fn map_row(row: &PgRow) -> NotificationDto {
    let actor_id: Option<Uuid> = row.get("actor_id");
    let actor_username: Option<String> = row.get("actor_username");
    let actor = actor_id.zip(actor_username).map(|(id, username)| ActorDto {
        id,
        username,
        avatar_url: row.get("actor_avatar_url"),
    });

    let post_id: Option<Uuid> = row.get("post_id");
    let post_snippet: Option<String> = row.get("post_snippet");
    let post = post_id
        .zip(post_snippet)
        .map(|(id, snippet)| PostSnippet { id, snippet });

    let read_at: Option<DateTime<Utc>> = row.get("read_at");

    NotificationDto {
        id: row.get("id"),
        kind: row.get::<String, _>("kind"),
        actor,
        post,
        comment_id: row.get("comment_id"),
        payload: row.get("payload"),
        read: read_at.is_some(),
        created_at: row.get("created_at"),
    }
}

// ── Query helpers ─────────────────────────────────────────────────────────────

/// Common SELECT columns shared by all list / insert-returning queries.
const BASE_SELECT: &str = r#"
    SELECT
        n.id,
        n.kind::text           AS kind,
        n.actor_id,
        u.username             AS actor_username,
        u.avatar_url           AS actor_avatar_url,
        n.post_id,
        LEFT(p.content, $SNIP$) AS post_snippet,
        n.comment_id,
        n.payload,
        n.read_at,
        n.created_at
    FROM notifications n
    LEFT JOIN users u ON u.id = n.actor_id
    LEFT JOIN posts p ON p.id = n.post_id
"#;

fn base_select() -> String {
    BASE_SELECT.replace("$SNIP$", &SNIPPET_LEN.to_string())
}

// ── Public functions ──────────────────────────────────────────────────────────

/// Cursor-based list of notifications for a user, newest first.
/// The cursor encodes `(created_at, id)` as produced by `crate::cursor`.
pub async fn list(
    db: &PgPool,
    user_id: Uuid,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
    unread_only: bool,
) -> anyhow::Result<Vec<NotificationDto>> {
    let base = base_select();

    let rows = match (unread_only, cursor) {
        (false, None) => {
            let q = format!(
                "{base} WHERE n.user_id = $1 \
                 ORDER BY n.created_at DESC, n.id DESC \
                 LIMIT $2"
            );
            sqlx::query(sqlx::AssertSqlSafe(q))
                .bind(user_id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
        (false, Some((ts, id))) => {
            let q = format!(
                "{base} WHERE n.user_id = $1 \
                 AND (n.created_at, n.id) < ($2, $3) \
                 ORDER BY n.created_at DESC, n.id DESC \
                 LIMIT $4"
            );
            sqlx::query(sqlx::AssertSqlSafe(q))
                .bind(user_id)
                .bind(ts)
                .bind(id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
        (true, None) => {
            let q = format!(
                "{base} WHERE n.user_id = $1 AND n.read_at IS NULL \
                 ORDER BY n.created_at DESC, n.id DESC \
                 LIMIT $2"
            );
            sqlx::query(sqlx::AssertSqlSafe(q))
                .bind(user_id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
        (true, Some((ts, id))) => {
            let q = format!(
                "{base} WHERE n.user_id = $1 AND n.read_at IS NULL \
                 AND (n.created_at, n.id) < ($2, $3) \
                 ORDER BY n.created_at DESC, n.id DESC \
                 LIMIT $4"
            );
            sqlx::query(sqlx::AssertSqlSafe(q))
                .bind(user_id)
                .bind(ts)
                .bind(id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
    };

    Ok(rows.iter().map(map_row).collect())
}

/// Mark a single notification as read. Returns `true` if the row was updated.
pub async fn mark_read(db: &PgPool, user_id: Uuid, notif_id: Uuid) -> anyhow::Result<bool> {
    let result = sqlx::query(
        r#"UPDATE notifications
           SET read_at = NOW()
           WHERE id = $1 AND user_id = $2 AND read_at IS NULL"#,
    )
    .bind(notif_id)
    .bind(user_id)
    .execute(db)
    .await
    .context("mark_read")?;
    Ok(result.rows_affected() > 0)
}

/// Mark all notifications for a user as read. Returns the number of rows updated.
pub async fn mark_all_read(db: &PgPool, user_id: Uuid) -> anyhow::Result<i64> {
    let result = sqlx::query(
        r#"UPDATE notifications
           SET read_at = NOW()
           WHERE user_id = $1 AND read_at IS NULL"#,
    )
    .bind(user_id)
    .execute(db)
    .await
    .context("mark_all_read")?;
    Ok(result.rows_affected() as i64)
}

/// Count unread notifications for a user (used for the DB fallback path).
pub async fn unread_count_db(db: &PgPool, user_id: Uuid) -> anyhow::Result<i64> {
    let row = sqlx::query(
        "SELECT COUNT(*)::bigint AS cnt FROM notifications WHERE user_id = $1 AND read_at IS NULL",
    )
    .bind(user_id)
    .fetch_one(db)
    .await
    .context("unread_count_db")?;
    Ok(row.get::<i64, _>("cnt"))
}

/// Insert a new notification and return the hydrated DTO.
#[allow(clippy::too_many_arguments)]
pub async fn insert(
    db: &PgPool,
    user_id: Uuid,
    kind: &str,
    actor_id: Option<Uuid>,
    post_id: Option<Uuid>,
    comment_id: Option<Uuid>,
    payload: serde_json::Value,
) -> anyhow::Result<NotificationDto> {
    // Insert and get back the new row's id + created_at so we can hydrate.
    let row = sqlx::query(
        r#"INSERT INTO notifications (user_id, kind, actor_id, post_id, comment_id, payload)
           VALUES ($1, $2::notification_kind, $3, $4, $5, $6)
           RETURNING id, created_at"#,
    )
    .bind(user_id)
    .bind(kind)
    .bind(actor_id)
    .bind(post_id)
    .bind(comment_id)
    .bind(&payload)
    .fetch_one(db)
    .await
    .context("insert notification")?;

    let id: Uuid = row.get("id");

    // Re-fetch with JOINs to produce a fully hydrated DTO.
    let base = base_select();
    let q = format!("{base} WHERE n.id = $1");
    let full_row = sqlx::query(sqlx::AssertSqlSafe(q))
        .bind(id)
        .fetch_one(db)
        .await
        .context("hydrate notification")?;

    Ok(map_row(&full_row))
}
