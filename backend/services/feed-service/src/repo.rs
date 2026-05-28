use anyhow::Context;
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::FeedPostRow;

/// Hydrate posts in the order of `ids`, dropping any whose status is not
/// `published` so caller never serves hidden/flagged content.
pub async fn hydrate_posts(db: &PgPool, ids: &[Uuid]) -> anyhow::Result<Vec<FeedPostRow>> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let rows: Vec<FeedPostRow> = sqlx::query_as(
        r#"
        SELECT
            p.id,
            p.author_id,
            u.username,
            u.display_name,
            u.avatar_url,
            p.content,
            p.media_urls,
            p.tags,
            p.topics,
            p.safety_score,
            p.like_count,
            p.comment_count,
            p.save_count,
            p.share_count,
            p.view_count,
            p.created_at
        FROM unnest($1::uuid[]) WITH ORDINALITY AS ids(id, ord)
        JOIN posts p ON p.id = ids.id
        JOIN users u ON u.id = p.author_id
        WHERE p.status = 'published'
        ORDER BY ids.ord
        "#,
    )
    .bind(ids)
    .fetch_all(db)
    .await
    .context("hydrate_posts")?;
    Ok(rows)
}

/// Posts by users the given user follows, newest first.
pub async fn following_feed(
    db: &PgPool,
    user_id: Uuid,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
) -> anyhow::Result<Vec<FeedPostRow>> {
    let rows: Vec<FeedPostRow> = match cursor {
        Some((ts, id)) => {
            sqlx::query_as(
                r#"
                SELECT
                    p.id, p.author_id, u.username, u.display_name, u.avatar_url,
                    p.content, p.media_urls, p.tags, p.topics, p.safety_score,
                    p.like_count, p.comment_count, p.save_count, p.share_count,
                    p.view_count, p.created_at
                FROM posts p
                JOIN follows f ON f.followee_id = p.author_id
                JOIN users u ON u.id = p.author_id
                WHERE f.follower_id = $1
                  AND p.status = 'published'
                  AND (p.created_at, p.id) < ($2, $3)
                ORDER BY p.created_at DESC
                LIMIT $4
                "#,
            )
            .bind(user_id)
            .bind(ts)
            .bind(id)
            .bind(limit)
            .fetch_all(db)
            .await
            .context("following_feed")?
        }
        None => {
            sqlx::query_as(
                r#"
                SELECT
                    p.id, p.author_id, u.username, u.display_name, u.avatar_url,
                    p.content, p.media_urls, p.tags, p.topics, p.safety_score,
                    p.like_count, p.comment_count, p.save_count, p.share_count,
                    p.view_count, p.created_at
                FROM posts p
                JOIN follows f ON f.followee_id = p.author_id
                JOIN users u ON u.id = p.author_id
                WHERE f.follower_id = $1
                  AND p.status = 'published'
                ORDER BY p.created_at DESC
                LIMIT $2
                "#,
            )
            .bind(user_id)
            .bind(limit)
            .fetch_all(db)
            .await
            .context("following_feed")?
        }
    };
    Ok(rows)
}

/// Most recent published posts; used as the last-resort fallback when neither
/// the cache nor the recommendation API nor Redis trending have items.
pub async fn recent_published(db: &PgPool, limit: i64) -> anyhow::Result<Vec<FeedPostRow>> {
    let rows: Vec<FeedPostRow> = sqlx::query_as(
        r#"
        SELECT
            p.id,
            p.author_id,
            u.username,
            u.display_name,
            u.avatar_url,
            p.content,
            p.media_urls,
            p.tags,
            p.topics,
            p.safety_score,
            p.like_count,
            p.comment_count,
            p.save_count,
            p.share_count,
            p.view_count,
            p.created_at
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE p.status = 'published'
        ORDER BY p.created_at DESC
        LIMIT $1
        "#,
    )
    .bind(limit)
    .fetch_all(db)
    .await
    .context("recent_published")?;
    Ok(rows)
}
