use axum::{
    extract::{Path, Query, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{sse::Event, IntoResponse, Response, Sse},
    Json,
};
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    events::Envelope,
    models::AuthUser,
};
use serde::Deserialize;
use std::{collections::HashMap, convert::Infallible, time::Duration};
use tokio_stream::wrappers::{BroadcastStream, IntervalStream};
use uuid::Uuid;

use crate::{events::*, repo, state::AppState};

fn current(s: &AppState, h: &HeaderMap) -> Option<AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw
        .split(';')
        .find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let c = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(AuthUser {
        id: c.sub,
        role: c.role,
    })
}

// --- like / save / share / hide ---

async fn toggle_post(
    s: AppState,
    h: HeaderMap,
    post_id: Uuid,
    type_: &'static str,
    method: &'static str,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let author = repo::post_author(&s.db, post_id)
        .await?
        .ok_or(AppError::NotFound {
            kind: "post".into(),
        })?;
    let weight = weight_for(type_);
    let mut tx = s.db.begin().await?;
    let changed = match method {
        "POST" => repo::insert_interaction(&mut tx, me.id, post_id, type_, weight).await?,
        "DELETE" => repo::delete_interaction(&mut tx, me.id, post_id, type_).await?,
        _ => unreachable!(),
    };
    if changed {
        if let Some(col) = counter_column(type_) {
            let delta = if method == "POST" { 1 } else { -1 };
            repo::bump_counter(&mut tx, post_id, col, delta).await?;
        }
    }
    tx.commit().await?;
    if changed {
        let evt = match (type_, method) {
            ("like", "POST") => "liked",
            ("like", "DELETE") => "unliked",
            ("save", "POST") => "saved",
            ("save", "DELETE") => "unsaved",
            ("share", "POST") => "shared",
            ("share", "DELETE") => "unshared",
            ("hide", "POST") => "hidden",
            ("hide", "DELETE") => "", // no event for unhide
            _ => "",
        };
        if !evt.is_empty() {
            let env = Envelope::new(
                evt,
                "interaction-service",
                ToggleData {
                    user_id: me.id,
                    post_id,
                    post_author_id: author,
                    weight,
                },
            );
            s.kafka
                .produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env)
                .await;
        }
    }
    let code = match (method, changed) {
        ("POST", true) => StatusCode::CREATED,
        ("POST", false) => StatusCode::OK,
        ("DELETE", _) => StatusCode::NO_CONTENT,
        _ => StatusCode::OK,
    };
    Ok(code)
}

pub async fn like_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "like", "POST").await
}
pub async fn unlike_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "like", "DELETE").await
}
pub async fn save_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "save", "POST").await
}
pub async fn unsave_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "save", "DELETE").await
}
pub async fn share_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "share", "POST").await
}
pub async fn unshare_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "share", "DELETE").await
}
pub async fn hide_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "hide", "POST").await
}
pub async fn unhide_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    toggle_post(s, h, id, "hide", "DELETE").await
}

// --- report ---

#[derive(Deserialize)]
pub struct ReportReq {
    pub reason: String,
    pub detail: Option<String>,
}

pub async fn report_post(
    State(s): State<AppState>,
    Path(post_id): Path<Uuid>,
    h: HeaderMap,
    Json(body): Json<ReportReq>,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let allowed = ["spam", "misinformation", "harassment", "nsfw", "other"];
    if !allowed.contains(&body.reason.as_str()) {
        return Err(AppError::Validation {
            field: "reason".into(),
            message: "invalid reason".into(),
        });
    }
    let author = repo::post_author(&s.db, post_id)
        .await?
        .ok_or(AppError::NotFound {
            kind: "post".into(),
        })?;
    let mut tx = s.db.begin().await?;
    let report_id = repo::insert_report(
        &mut tx,
        me.id,
        post_id,
        &body.reason,
        body.detail.as_deref(),
    )
    .await?;
    repo::insert_interaction(&mut tx, me.id, post_id, "report", weight_for("report")).await?;
    tx.commit().await?;
    let env = Envelope::new(
        "reported",
        "interaction-service",
        ReportData {
            reporter_id: me.id,
            post_id,
            post_author_id: author,
            reason: body.reason,
            report_id,
        },
    );
    s.kafka
        .produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env)
        .await;
    Ok(StatusCode::CREATED)
}

// --- comments ---

#[derive(Deserialize)]
pub struct CommentReq {
    pub content: String,
    pub parent_comment_id: Option<Uuid>,
}
#[derive(Deserialize)]
pub struct CommentsPage {
    pub limit: Option<i64>,
}

pub async fn create_comment(
    State(s): State<AppState>,
    Path(post_id): Path<Uuid>,
    h: HeaderMap,
    Json(body): Json<CommentReq>,
) -> AppResult<Json<serde_json::Value>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let content = body.content.trim();
    if content.is_empty() || content.chars().count() > 2000 {
        return Err(AppError::Validation {
            field: "content".into(),
            message: "1..=2000 chars".into(),
        });
    }
    let author = repo::post_author(&s.db, post_id)
        .await?
        .ok_or(AppError::NotFound {
            kind: "post".into(),
        })?;
    let mut tx = s.db.begin().await?;
    let comment_id =
        repo::insert_comment(&mut tx, post_id, me.id, body.parent_comment_id, content).await?;
    if body.parent_comment_id.is_none() {
        repo::bump_counter(&mut tx, post_id, "comment_count", 1).await?;
    }
    tx.commit().await?;
    let preview = content.chars().take(200).collect::<String>();
    let event_type = if body.parent_comment_id.is_some() {
        "comment_replied"
    } else {
        "commented"
    };
    let env = Envelope::new(
        event_type,
        "interaction-service",
        CommentData {
            commenter_id: me.id,
            post_id,
            post_author_id: author,
            comment_id,
            parent_comment_id: body.parent_comment_id,
            content_preview: preview,
        },
    );
    s.kafka
        .produce_json(TOPIC_INTERACTIONS, post_id.to_string().as_str(), &env)
        .await;
    // Fan out to live SSE subscribers for this post.
    if let Some(dto) = repo::fetch_comment_dto(&s.db, comment_id).await? {
        s.comment_fanout.publish(post_id, dto);
    }
    Ok(Json(
        serde_json::json!({ "id": comment_id, "parent_comment_id": body.parent_comment_id }),
    ))
}

pub async fn list_comments(
    State(s): State<AppState>,
    Path(post_id): Path<Uuid>,
    Query(q): Query<CommentsPage>,
) -> AppResult<Json<Vec<serde_json::Value>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let top = repo::list_top_level_comments(&s.db, post_id, limit).await?;
    let mut out = Vec::with_capacity(top.len());
    for c in top {
        // load up to 5 replies inline
        let replies = repo::list_replies(&s.db, c.id, 5).await?;
        let has_more = replies.len() == 5 && c.reply_count > 5;
        out.push(serde_json::json!({
            "id": c.id, "post_id": c.post_id, "author_id": c.author_id,
            "author_username": c.author_username, "author_display_name": c.author_display_name,
            "parent_comment_id": c.parent_comment_id,
            "content": c.content, "is_deleted": c.is_deleted, "created_at": c.created_at,
            "reply_count": c.reply_count, "has_more_replies": has_more,
            "replies": replies.iter().map(|r| serde_json::json!({
                "id": r.id, "post_id": r.post_id, "author_id": r.author_id,
                "author_username": r.author_username, "author_display_name": r.author_display_name,
                "parent_comment_id": r.parent_comment_id, "content": r.content,
                "is_deleted": r.is_deleted, "created_at": r.created_at,
            })).collect::<Vec<_>>(),
        }));
    }
    Ok(Json(out))
}

pub async fn list_comment_replies(
    State(s): State<AppState>,
    Path(comment_id): Path<Uuid>,
    Query(q): Query<CommentsPage>,
) -> AppResult<Json<Vec<repo::CommentRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_replies(&s.db, comment_id, limit).await?))
}

pub async fn delete_comment(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let mut tx = s.db.begin().await?;
    let (post_id, was_top) = repo::soft_delete_comment(&mut tx, id, me).await?;
    if was_top {
        repo::bump_counter(&mut tx, post_id, "comment_count", -1).await?;
    }
    tx.commit().await?;
    Ok(StatusCode::NO_CONTENT)
}

// --- GET /api/v1/posts/{id}/comments/stream (SSE) ---

const SSE_HEARTBEAT_SECS: u64 = 30;

pub async fn comments_sse_stream(
    State(state): State<AppState>,
    Path(post_id): Path<Uuid>,
    h: HeaderMap,
) -> Result<Response, AppError> {
    let _me = current(&state, &h).ok_or(AppError::Unauthorized)?;
    let rx = state.comment_fanout.subscribe(post_id);
    let heartbeat_interval = Duration::from_secs(SSE_HEARTBEAT_SECS);

    let comment_stream =
        futures_util::StreamExt::filter_map(BroadcastStream::new(rx), |result| async move {
            match result {
                Ok(dto) => {
                    let data = serde_json::to_string(&dto).unwrap_or_default();
                    Some(Ok::<Event, Infallible>(
                        Event::default().event("comment").data(data),
                    ))
                }
                Err(_) => None,
            }
        });

    let heartbeat_stream = futures_util::StreamExt::map(
        futures_util::StreamExt::skip(
            IntervalStream::new(tokio::time::interval(heartbeat_interval)),
            1,
        ),
        |_| Ok::<Event, Infallible>(Event::default().event("heartbeat").data("ping")),
    );

    let merged = futures_util::stream::select(comment_stream, heartbeat_stream);

    let sse =
        Sse::new(merged).keep_alive(axum::response::sse::KeepAlive::new().interval(heartbeat_interval).text("ping"));

    Ok((
        [
            (header::CACHE_CONTROL, HeaderValue::from_static("no-store")),
            (
                header::HeaderName::from_static("x-accel-buffering"),
                HeaderValue::from_static("no"),
            ),
        ],
        sse,
    )
        .into_response())
}

// --- saved posts ---

#[derive(Deserialize)]
pub struct SavedQuery {
    pub cursor: Option<String>,
    pub limit: Option<i64>,
}

#[derive(serde::Serialize)]
pub struct SavedResponse {
    pub items: Vec<repo::SavedPostRow>,
    pub next_cursor: Option<String>,
}

pub async fn list_saved_posts(
    State(s): State<AppState>,
    h: HeaderMap,
    Query(q): Query<SavedQuery>,
) -> AppResult<Json<SavedResponse>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let cursor_pair = q.cursor.as_deref().and_then(|c| {
        let mut parts = c.splitn(2, '|');
        let ts = parts.next()?;
        let id = parts.next()?;
        let dt = chrono::DateTime::parse_from_rfc3339(ts).ok()?.with_timezone(&chrono::Utc);
        let uuid = Uuid::parse_str(id).ok()?;
        Some((dt, uuid))
    });
    let rows = repo::list_saved_posts(&s.db, me.id, cursor_pair, limit).await?;
    let next = if rows.len() as i64 == limit {
        rows.last().map(|r| format!("{}|{}", r.saved_at.to_rfc3339(), r.id))
    } else {
        None
    };
    Ok(Json(SavedResponse {
        items: rows,
        next_cursor: next,
    }))
}

// --- my interactions ---

#[derive(Deserialize)]
pub struct BatchMeRequest {
    pub post_ids: Vec<Uuid>,
}

#[derive(serde::Serialize)]
pub struct BatchMeResponse {
    pub items: HashMap<Uuid, repo::MyInteractionState>,
}

pub async fn my_post_interactions(
    State(s): State<AppState>,
    Path(post_id): Path<Uuid>,
    h: HeaderMap,
) -> AppResult<Json<repo::MyInteractions>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    Ok(Json(repo::my_interactions(&s.db, me.id, post_id).await?))
}

pub async fn batch_me(
    State(s): State<AppState>,
    h: HeaderMap,
    Json(body): Json<BatchMeRequest>,
) -> AppResult<Json<BatchMeResponse>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    if body.post_ids.is_empty() || body.post_ids.len() > 100 {
        return Err(AppError::Validation {
            field: "post_ids".into(),
            message: "1..=100 items".into(),
        });
    }
    Ok(Json(BatchMeResponse {
        items: repo::batch_my_interactions(&s.db, me.id, &body.post_ids).await?,
    }))
}
