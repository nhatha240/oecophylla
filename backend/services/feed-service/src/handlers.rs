use axum::{
    extract::{Query, State},
    http::HeaderMap,
    Json,
};
use chrono::Utc;
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    models::AuthUser,
};
use uuid::Uuid;

use crate::{
    cache::{get_cached_feed, set_cached_feed, trending_ids},
    recommendation::{recommend_feed, RecommendFeedRequest, RecommendationItem},
    repo,
    state::AppState,
    types::{
        CachedFeed, CachedFeedItem, FeedItem, FeedPostRow, FeedQuery, FeedRank, FeedResponse,
    },
};

const DEFAULT_PAGE_SIZE: usize = 20;
const MAX_PAGE_SIZE: usize = 50;

fn current(s: &AppState, h: &HeaderMap) -> Option<AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw
        .split(';')
        .find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let claims = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(AuthUser {
        id: claims.sub,
        role: claims.role,
    })
}

pub async fn get_feed(
    State(s): State<AppState>,
    Query(q): Query<FeedQuery>,
    h: HeaderMap,
) -> AppResult<Json<FeedResponse>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let limit = q
        .limit
        .unwrap_or(DEFAULT_PAGE_SIZE)
        .clamp(1, MAX_PAGE_SIZE);
    let cursor_offset = parse_cursor(q.cursor.as_deref());

    let (cached, source) = load_or_build_feed(&s, me.id).await;
    let total = cached.items.len();
    let slice_end = (cursor_offset + limit).min(total);
    let slice = if cursor_offset >= total {
        &[][..]
    } else {
        &cached.items[cursor_offset..slice_end]
    };

    let ids: Vec<Uuid> = slice.iter().map(|x| x.post_id).collect();
    let posts = repo::hydrate_posts(&s.db, &ids)
        .await
        .map_err(AppError::Other)?;

    let items = posts
        .into_iter()
        .filter_map(|post| {
            let meta = slice.iter().find(|c| c.post_id == post.id)?;
            Some(FeedItem {
                rank: FeedRank {
                    score: meta.score,
                    source: meta.source.clone(),
                    reason: meta.reason.clone(),
                },
                post,
            })
        })
        .collect::<Vec<_>>();

    let next_cursor = if slice_end < total {
        Some(slice_end.to_string())
    } else {
        None
    };

    Ok(Json(FeedResponse {
        items,
        next_cursor,
        source,
        generated_at: cached.generated_at,
    }))
}

/// Fallback ladder: cache → recommendation-api → Redis trending → recent published.
/// Returns (cached_payload, response_source). The response source distinguishes
/// `cache` (already in Redis) from the freshly built sources so clients can
/// observe fallback cleanly.
async fn load_or_build_feed(s: &AppState, user_id: Uuid) -> (CachedFeed, String) {
    if let Ok(Some(feed)) = get_cached_feed(&s.redis, user_id).await {
        return (feed, "cache".into());
    }

    let cfg = s.feed_cfg.as_ref();
    let req = RecommendFeedRequest {
        limit: cfg.feed_result_size,
        candidate_pool: cfg.feed_candidate_pool,
        exclude_post_ids: vec![],
    };
    match recommend_feed(
        &s.http,
        &cfg.recommendation_url,
        user_id,
        req,
        cfg.recommendation_timeout_ms,
    )
    .await
    {
        Ok(items) if !items.is_empty() => {
            let cached = build_cached_feed("personalized", items);
            persist(s, user_id, &cached).await;
            (cached, "personalized".into())
        }
        Ok(_) => fallback_feed(s, user_id).await,
        Err(err) => {
            tracing::warn!(error = %err, %user_id, "recommendation-api unavailable, falling back");
            fallback_feed(s, user_id).await
        }
    }
}

async fn fallback_feed(s: &AppState, user_id: Uuid) -> (CachedFeed, String) {
    let cfg = s.feed_cfg.as_ref();
    if let Ok(ids) = trending_ids(&s.redis, cfg.feed_result_size).await {
        if !ids.is_empty() {
            let items = ids
                .into_iter()
                .map(|post_id| RecommendationItem {
                    post_id,
                    score: 0.0,
                    source: "trending".into(),
                    reason: "redis-zset".into(),
                })
                .collect();
            let cached = build_cached_feed("fallback", items);
            persist(s, user_id, &cached).await;
            return (cached, "fallback".into());
        }
    }

    let rows = repo::recent_published(&s.db, cfg.feed_result_size as i64)
        .await
        .unwrap_or_default();
    let items = rows
        .iter()
        .map(|p: &FeedPostRow| RecommendationItem {
            post_id: p.id,
            score: 0.0,
            source: "recent".into(),
            reason: "fallback-recent".into(),
        })
        .collect();
    let cached = build_cached_feed("fallback", items);
    // Cache the fallback at a shorter TTL by reusing the configured TTL — when
    // the recommender comes back online the cache-invalidator wipes per-user
    // entries on interactions.
    persist(s, user_id, &cached).await;
    (cached, "fallback".into())
}

fn build_cached_feed(source: &str, items: Vec<RecommendationItem>) -> CachedFeed {
    CachedFeed {
        generated_at: Utc::now(),
        source: source.into(),
        items: items
            .into_iter()
            .map(|i| CachedFeedItem {
                post_id: i.post_id,
                score: i.score,
                source: i.source,
                reason: i.reason,
            })
            .collect(),
    }
}

async fn persist(s: &AppState, user_id: Uuid, feed: &CachedFeed) {
    if let Err(err) =
        set_cached_feed(&s.redis, user_id, feed, s.feed_cfg.feed_cache_ttl_seconds).await
    {
        tracing::warn!(error = %err, %user_id, "failed to cache feed");
    }
}

fn parse_cursor(raw: Option<&str>) -> usize {
    raw.and_then(|s| s.parse::<usize>().ok()).unwrap_or(0)
}
