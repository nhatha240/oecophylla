use std::convert::Infallible;
use std::time::Duration;

use axum::{
    extract::{Extension, Path, Query, State},
    http::{header, HeaderValue},
    response::{
        sse::{Event, KeepAlive, Sse},
        IntoResponse,
    },
    Json,
};
use common::{error::AppError, models::AuthUser};
use tokio_stream::wrappers::{BroadcastStream, IntervalStream};
use uuid::Uuid;

use crate::{
    cache, cursor, repo,
    state::AppState,
    types::{
        ListQuery, MarkAllReadResponse, NotificationDto, NotificationListResponse,
        UnreadCountResponse,
    },
};

// ── GET /api/v1/notifications ─────────────────────────────────────────────────

pub async fn list_notifications(
    State(state): State<AppState>,
    Extension(user): Extension<AuthUser>,
    Query(q): Query<ListQuery>,
) -> Result<impl IntoResponse, AppError> {
    let cursor_pair = q.cursor.as_deref().and_then(cursor::decode);

    let limit = q.limit.clamp(1, 100);

    let items = repo::list(&state.db, user.id, cursor_pair, limit, q.unread_only).await?;

    let next_cursor = if items.len() as i64 == limit {
        items.last().map(|n| cursor::encode(n.created_at, n.id))
    } else {
        None
    };

    Ok(Json(NotificationListResponse { items, next_cursor }))
}

// ── POST /api/v1/notifications/:id/read ───────────────────────────────────────

pub async fn mark_read(
    State(state): State<AppState>,
    Extension(user): Extension<AuthUser>,
    Path(id): Path<Uuid>,
) -> Result<impl IntoResponse, AppError> {
    let updated = repo::mark_read(&state.db, user.id, id).await?;

    if updated {
        if let Err(e) = cache::invalidate_unread_count(&state.redis, user.id).await {
            tracing::warn!(error = %e, user_id = %user.id, "failed to invalidate unread cache");
        }
    }

    Ok(axum::http::StatusCode::NO_CONTENT)
}

// ── POST /api/v1/notifications/read-all ───────────────────────────────────────

pub async fn mark_all_read(
    State(state): State<AppState>,
    Extension(user): Extension<AuthUser>,
) -> Result<impl IntoResponse, AppError> {
    let count = repo::mark_all_read(&state.db, user.id).await?;

    if count > 0 {
        if let Err(e) = cache::invalidate_unread_count(&state.redis, user.id).await {
            tracing::warn!(error = %e, user_id = %user.id, "failed to invalidate unread cache");
        }
    }

    Ok(Json(MarkAllReadResponse { count }))
}

// ── GET /api/v1/notifications/unread-count ────────────────────────────────────

pub async fn unread_count(
    State(state): State<AppState>,
    Extension(user): Extension<AuthUser>,
) -> Result<impl IntoResponse, AppError> {
    let count = match cache::unread_count(&state.redis, user.id).await {
        Ok(Some(n)) => n,
        _ => {
            // Cache miss or Redis error — fall through to DB.
            let n = repo::unread_count_db(&state.db, user.id).await?;
            // Best-effort cache population; ignore errors.
            let _ = cache::set_unread_count(&state.redis, user.id, n).await;
            n
        }
    };

    Ok(Json(UnreadCountResponse { count }))
}

// ── GET /api/v1/notifications/stream (SSE) ────────────────────────────────────

pub async fn sse_stream(
    State(state): State<AppState>,
    Extension(user): Extension<AuthUser>,
) -> impl IntoResponse {
    let rx = state.fanout.subscribe(user.id);
    let heartbeat_interval = Duration::from_secs(state.notif_cfg.sse_heartbeat_seconds);

    // Turn the broadcast receiver into a Stream of SSE events.
    let notification_stream =
        futures_util::StreamExt::filter_map(BroadcastStream::new(rx), |result| async move {
            match result {
                Ok(dto) => {
                    let data = serde_json::to_string(&dto).unwrap_or_default();
                    Some(Ok::<Event, Infallible>(
                        Event::default().event("notification").data(data),
                    ))
                }
                // Receiver lagged (missed messages) — skip silently.
                Err(_) => None,
            }
        });

    // Heartbeat stream using tokio interval — skip the first immediate tick.
    let heartbeat_stream = futures_util::StreamExt::map(
        futures_util::StreamExt::skip(
            IntervalStream::new(tokio::time::interval(heartbeat_interval)),
            1,
        ),
        |_| Ok::<Event, Infallible>(Event::default().event("heartbeat").data("ping")),
    );

    let merged = futures_util::stream::select(notification_stream, heartbeat_stream);

    let sse =
        Sse::new(merged).keep_alive(KeepAlive::new().interval(heartbeat_interval).text("ping"));

    // Attach cache-control and proxy-buffering headers to the response.
    (
        [
            (header::CACHE_CONTROL, HeaderValue::from_static("no-store")),
            (
                header::HeaderName::from_static("x-accel-buffering"),
                HeaderValue::from_static("no"),
            ),
        ],
        sse,
    )
        .into_response()
}

// ── Internal helper used by the Kafka consumer ────────────────────────────────

/// Persist a notification and push it to any live SSE connections.
pub async fn dispatch_notification(
    state: &AppState,
    user_id: Uuid,
    kind: &str,
    actor_id: Option<Uuid>,
    post_id: Option<Uuid>,
    comment_id: Option<Uuid>,
    payload: serde_json::Value,
) -> anyhow::Result<()> {
    let dto: NotificationDto = repo::insert(
        &state.db, user_id, kind, actor_id, post_id, comment_id, payload,
    )
    .await?;

    state.fanout.publish(user_id, dto);

    cache::invalidate_unread_count(&state.redis, user_id).await?;

    Ok(())
}
