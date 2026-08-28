use anyhow::Context;
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::FeedPostRow;

#[derive(Debug)]
pub struct NewRecommendationImpression {
    pub id: Uuid,
    pub post_id: Uuid,
    pub position: i16,
    pub candidate_source: String,
    pub score: Option<f32>,
    pub feature_snapshot: String,
}

/// Insert one served page with a single set-based statement. The request,
/// authenticated user, feed source and model version are shared by every row.
pub async fn insert_recommendation_impressions(
    db: &PgPool,
    request_id: Uuid,
    user_id: Uuid,
    feed_source: &str,
    model_version: &str,
    impressions: &[NewRecommendationImpression],
) -> anyhow::Result<()> {
    if impressions.is_empty() {
        return Ok(());
    }

    let ids = impressions.iter().map(|item| item.id).collect::<Vec<_>>();
    let post_ids = impressions
        .iter()
        .map(|item| item.post_id)
        .collect::<Vec<_>>();
    let positions = impressions
        .iter()
        .map(|item| item.position)
        .collect::<Vec<_>>();
    let candidate_sources = impressions
        .iter()
        .map(|item| item.candidate_source.as_str())
        .collect::<Vec<_>>();
    let scores = impressions
        .iter()
        .map(|item| item.score)
        .collect::<Vec<_>>();
    let feature_snapshots = impressions
        .iter()
        .map(|item| item.feature_snapshot.as_str())
        .collect::<Vec<_>>();

    let result = sqlx::query(
        r#"
        INSERT INTO recommendation_impressions (
            id,
            request_id,
            user_id,
            post_id,
            position,
            feed_source,
            candidate_source,
            score,
            model_version,
            feature_snapshot
        )
        SELECT
            batch.id,
            $1,
            $2,
            batch.post_id,
            batch.position,
            $3,
            batch.candidate_source,
            batch.score,
            $4,
            batch.feature_snapshot::jsonb
        FROM UNNEST(
            $5::uuid[],
            $6::uuid[],
            $7::smallint[],
            $8::text[],
            $9::real[],
            $10::text[]
        ) AS batch(
            id,
            post_id,
            position,
            candidate_source,
            score,
            feature_snapshot
        )
        "#,
    )
    .bind(request_id)
    .bind(user_id)
    .bind(feed_source)
    .bind(model_version)
    .bind(ids)
    .bind(post_ids)
    .bind(positions)
    .bind(candidate_sources)
    .bind(scores)
    .bind(feature_snapshots)
    .execute(db)
    .await
    .context("insert recommendation impressions batch")?;

    if result.rows_affected() != impressions.len() as u64 {
        anyhow::bail!(
            "inserted {} recommendation impressions, expected {}",
            result.rows_affected(),
            impressions.len()
        );
    }
    Ok(())
}

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
        Some((ts, id)) => sqlx::query_as(
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
        .context("following_feed")?,
        None => sqlx::query_as(
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
        .context("following_feed")?,
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
