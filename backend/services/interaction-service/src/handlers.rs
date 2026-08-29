use axum::{
    extract::{Path, Query, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{sse::Event, IntoResponse, Response, Sse},
    Json,
};
use chrono::{DateTime, Duration as ChronoDuration, Utc};
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    events::Envelope,
    models::AuthUser,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    convert::Infallible,
    time::Duration,
};
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

const MAX_BEHAVIOR_BATCH_SIZE: usize = 100;
const MAX_DWELL_MS: i32 = 1_800_000;
const MIN_QUALIFIED_VIEW_MS: i32 = 5_000;
const MAX_METADATA_BYTES: usize = 8_192;

#[derive(Deserialize)]
pub struct BehaviorBatchRequest {
    pub events: Vec<serde_json::Value>,
}

#[derive(Deserialize)]
struct RawBehaviorEvent {
    client_event_id: Uuid,
    post_id: Uuid,
    #[serde(default)]
    impression_id: Option<Uuid>,
    #[serde(default)]
    session_id: Option<Uuid>,
    event_type: String,
    #[serde(default)]
    dwell_ms: Option<i32>,
    #[serde(default = "empty_metadata")]
    metadata: serde_json::Value,
    occurred_at: DateTime<Utc>,
}

fn empty_metadata() -> serde_json::Value {
    serde_json::json!({})
}

#[derive(Serialize)]
pub struct BehaviorBatchResponse {
    pub accepted: usize,
    pub duplicate: usize,
    pub rejected: usize,
    pub errors: Vec<BehaviorEventError>,
}

#[derive(Serialize)]
pub struct BehaviorEventError {
    pub index: usize,
    pub code: &'static str,
    pub message: String,
}

struct ValidatedBehaviorEvent {
    index: usize,
    event: repo::NewBehaviorEvent,
    positive_signal: bool,
}

struct EventValidationError {
    code: &'static str,
    message: String,
}

pub async fn ingest_behavior_events(
    State(s): State<AppState>,
    h: HeaderMap,
    Json(body): Json<BehaviorBatchRequest>,
) -> AppResult<Json<BehaviorBatchResponse>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    if body.events.is_empty() || body.events.len() > MAX_BEHAVIOR_BATCH_SIZE {
        return Err(AppError::Validation {
            field: "events".into(),
            message: "1..=100 items".into(),
        });
    }

    let now = Utc::now();
    let mut errors = Vec::new();
    let mut parsed = Vec::with_capacity(body.events.len());
    for (index, value) in body.events.into_iter().enumerate() {
        let raw = match serde_json::from_value::<RawBehaviorEvent>(value) {
            Ok(raw) => raw,
            Err(error) => {
                errors.push(BehaviorEventError {
                    index,
                    code: "invalid_event",
                    message: error.to_string(),
                });
                continue;
            }
        };
        match validate_behavior_event(index, raw, now, s.positive_dwell_ms) {
            Ok(event) => parsed.push(event),
            Err(error) => errors.push(BehaviorEventError {
                index,
                code: error.code,
                message: error.message,
            }),
        }
    }

    let mut duplicate = 0usize;
    let mut seen_client_ids = HashSet::new();
    parsed.retain(|item| {
        if seen_client_ids.insert(item.event.client_event_id) {
            true
        } else {
            duplicate += 1;
            false
        }
    });

    let mut tx =
        s.db.begin()
            .await
            .map_err(AppError::Db)
            .map_err(record_behavior_ingest_error)?;
    let existing_posts = repo::existing_post_ids(
        &mut tx,
        &parsed
            .iter()
            .map(|item| item.event.post_id)
            .collect::<Vec<_>>(),
    )
    .await
    .map_err(record_behavior_ingest_error)?;
    parsed.retain(|item| {
        if existing_posts.contains(&item.event.post_id) {
            true
        } else {
            errors.push(BehaviorEventError {
                index: item.index,
                code: "post_not_found",
                message: "post does not exist".into(),
            });
            false
        }
    });

    let impression_references = parsed
        .iter()
        .filter_map(|item| item.event.impression_id.map(|id| (id, item.event.post_id)))
        .collect::<Vec<_>>();
    let valid_impressions = repo::valid_impression_ids(&mut tx, me.id, &impression_references)
        .await
        .map_err(record_behavior_ingest_error)?;
    parsed.retain(|item| match item.event.impression_id {
        Some(impression_id) if !valid_impressions.contains(&impression_id) => {
            errors.push(BehaviorEventError {
                index: item.index,
                code: "impression_mismatch",
                message: "impression does not belong to the authenticated user and post".into(),
            });
            false
        }
        _ => true,
    });

    let inserted = repo::insert_behavior_events(
        &mut tx,
        me.id,
        &parsed
            .iter()
            .map(|item| repo::NewBehaviorEvent {
                id: item.event.id,
                client_event_id: item.event.client_event_id,
                post_id: item.event.post_id,
                impression_id: item.event.impression_id,
                session_id: item.event.session_id,
                event_type: item.event.event_type.clone(),
                dwell_ms: item.event.dwell_ms,
                metadata: item.event.metadata.clone(),
                occurred_at: item.event.occurred_at,
            })
            .collect::<Vec<_>>(),
    )
    .await
    .map_err(record_behavior_ingest_error)?;

    if s.behavior_view_counter_enabled {
        let viewed_post_ids = inserted
            .iter()
            .filter(|event| event.event_type == "view")
            .map(|event| event.post_id)
            .collect::<Vec<_>>();
        repo::bump_view_counts(&mut tx, &viewed_post_ids)
            .await
            .map_err(record_behavior_ingest_error)?;
    }
    tx.commit()
        .await
        .map_err(AppError::Db)
        .map_err(record_behavior_ingest_error)?;

    let inserted_ids = inserted
        .iter()
        .map(|event| event.client_event_id)
        .collect::<HashSet<_>>();
    duplicate += parsed.len().saturating_sub(inserted.len());
    let positive_ids = parsed
        .iter()
        .filter(|item| item.positive_signal)
        .map(|item| item.event.client_event_id)
        .collect::<HashSet<_>>();
    for event in inserted
        .iter()
        .filter(|event| positive_ids.contains(&event.client_event_id))
    {
        let kafka = s.kafka.clone();
        let post_key = event.post_id.to_string();
        let envelope = viewed_envelope(BehaviorTelemetryData {
            user_id: me.id,
            post_id: event.post_id,
            client_event_id: event.client_event_id,
            behavior_event_id: event.id,
            impression_id: event.impression_id,
            session_id: event.session_id,
            occurred_at: event.occurred_at,
        });
        tokio::spawn(async move {
            kafka
                .produce_json(TOPIC_INTERACTIONS, &post_key, &envelope)
                .await;
        });
    }

    errors.sort_by_key(|error| error.index);
    let accepted = inserted_ids.len();
    let rejected = errors.len();
    metrics::counter!("behavior_events_accepted_total").increment(accepted as u64);
    metrics::counter!("behavior_events_duplicate_total").increment(duplicate as u64);
    metrics::counter!("behavior_events_rejected_total").increment(rejected as u64);
    for event in &inserted {
        let lag_seconds = now
            .signed_duration_since(event.occurred_at)
            .num_milliseconds()
            .max(0) as f64
            / 1000.0;
        metrics::histogram!(
            "behavior_event_ingest_lag_seconds",
            "event_type" => event.event_type.clone(),
        )
        .record(lag_seconds);
    }
    Ok(Json(BehaviorBatchResponse {
        accepted,
        duplicate,
        rejected,
        errors,
    }))
}

fn validate_behavior_event(
    index: usize,
    raw: RawBehaviorEvent,
    now: DateTime<Utc>,
    positive_dwell_ms: i32,
) -> Result<ValidatedBehaviorEvent, EventValidationError> {
    if !(0..=MAX_DWELL_MS).contains(&raw.dwell_ms.unwrap_or(0)) {
        return Err(validation_error(
            "invalid_dwell_ms",
            format!("dwell_ms must be between 0 and {MAX_DWELL_MS}"),
        ));
    }
    let metadata = raw
        .metadata
        .as_object()
        .ok_or_else(|| validation_error("invalid_metadata", "metadata must be a JSON object"))?;
    if serde_json::to_vec(&raw.metadata)
        .map_err(|error| validation_error("invalid_metadata", error.to_string()))?
        .len()
        > MAX_METADATA_BYTES
    {
        return Err(validation_error(
            "metadata_too_large",
            "metadata must not exceed 8192 bytes",
        ));
    }

    let mut positive_signal = false;
    match raw.event_type.as_str() {
        "visible" => {
            require_metadata_keys(metadata, &["viewport_ratio"])?;
            if raw.dwell_ms.is_some() {
                return Err(validation_error(
                    "invalid_dwell_ms",
                    "visible must not include dwell_ms",
                ));
            }
            let ratio = metadata
                .get("viewport_ratio")
                .and_then(|value| value.as_f64())
                .ok_or_else(|| {
                    validation_error(
                        "invalid_metadata",
                        "visible requires numeric viewport_ratio",
                    )
                })?;
            if !(0.5..=1.0).contains(&ratio) {
                return Err(validation_error(
                    "invalid_metadata",
                    "viewport_ratio must be between 0.5 and 1.0",
                ));
            }
        }
        "view" => {
            require_metadata_keys(metadata, &["continuous_visible_ms", "trigger"])?;
            let trigger = metadata
                .get("trigger")
                .and_then(|value| value.as_str())
                .ok_or_else(|| validation_error("invalid_metadata", "view requires trigger"))?;
            if !["feed", "detail"].contains(&trigger) {
                return Err(validation_error(
                    "invalid_metadata",
                    "view trigger must be feed or detail",
                ));
            }
            let continuous_ms = metadata
                .get("continuous_visible_ms")
                .and_then(|value| value.as_i64())
                .unwrap_or(0);
            if !(0..=MAX_DWELL_MS as i64).contains(&continuous_ms) {
                return Err(validation_error(
                    "invalid_metadata",
                    "continuous_visible_ms is out of range",
                ));
            }
            let measured_ms = continuous_ms.max(raw.dwell_ms.unwrap_or(0) as i64);
            if trigger == "feed" && measured_ms < MIN_QUALIFIED_VIEW_MS as i64 {
                return Err(validation_error(
                    "unqualified_view",
                    "feed view requires at least 5000 ms continuous visibility",
                ));
            }
            positive_signal = measured_ms >= positive_dwell_ms as i64;
        }
        "click" => {
            require_metadata_keys(metadata, &["target"])?;
            if raw.dwell_ms.is_some()
                || metadata.get("target").and_then(|value| value.as_str()) != Some("post_detail")
            {
                return Err(validation_error(
                    "invalid_metadata",
                    "click requires target=post_detail and no dwell_ms",
                ));
            }
        }
        "dwell" => {
            require_metadata_keys(metadata, &["trigger"])?;
            if raw.dwell_ms.is_none() {
                return Err(validation_error(
                    "invalid_dwell_ms",
                    "dwell requires dwell_ms",
                ));
            }
            let trigger = metadata.get("trigger").and_then(|value| value.as_str());
            if !matches!(trigger, Some("viewport_exit" | "page_hidden" | "destroy")) {
                return Err(validation_error(
                    "invalid_metadata",
                    "dwell trigger must be viewport_exit, page_hidden, or destroy",
                ));
            }
        }
        _ => {
            return Err(validation_error(
                "invalid_event_type",
                "event_type must be visible, view, click, or dwell",
            ));
        }
    }

    let occurred_at = raw
        .occurred_at
        .max(now - ChronoDuration::hours(24))
        .min(now + ChronoDuration::minutes(5));
    Ok(ValidatedBehaviorEvent {
        index,
        event: repo::NewBehaviorEvent {
            id: Uuid::now_v7(),
            client_event_id: raw.client_event_id,
            post_id: raw.post_id,
            impression_id: raw.impression_id,
            session_id: raw.session_id,
            event_type: raw.event_type,
            dwell_ms: raw.dwell_ms,
            metadata: serde_json::to_string(&raw.metadata)
                .map_err(|error| validation_error("invalid_metadata", error.to_string()))?,
            occurred_at,
        },
        positive_signal,
    })
}

fn require_metadata_keys(
    metadata: &serde_json::Map<String, serde_json::Value>,
    allowed: &[&str],
) -> Result<(), EventValidationError> {
    if let Some(key) = metadata.keys().find(|key| !allowed.contains(&key.as_str())) {
        return Err(validation_error(
            "unknown_metadata_key",
            format!("metadata key {key} is not allowed"),
        ));
    }
    Ok(())
}

fn validation_error(code: &'static str, message: impl Into<String>) -> EventValidationError {
    EventValidationError {
        code,
        message: message.into(),
    }
}

fn record_behavior_ingest_error(error: AppError) -> AppError {
    metrics::counter!("behavior_events_errors_total").increment(1);
    error
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
    let behavior_event_id = if changed {
        let event_type = match (type_, method) {
            ("like", "POST") => "like",
            ("like", "DELETE") => "unlike",
            ("save", "POST") => "save",
            ("save", "DELETE") => "unsave",
            ("share", "POST") => "share",
            ("share", "DELETE") => "unshare",
            ("hide", "POST") => "hide",
            ("hide", "DELETE") => "unhide",
            _ => unreachable!(),
        };
        Some(repo::insert_canonical_behavior_event(&mut tx, me.id, post_id, event_type).await?)
    } else {
        None
    };
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
                    client_event_id: behavior_event_id.expect("changed action has behavior event"),
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
    let behavior_event_id =
        repo::insert_canonical_behavior_event(&mut tx, me.id, post_id, "report").await?;
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
            client_event_id: behavior_event_id,
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
    let behavior_event_id =
        repo::insert_canonical_behavior_event(&mut tx, me.id, post_id, "comment").await?;
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
            client_event_id: behavior_event_id,
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

    let sse = Sse::new(merged).keep_alive(
        axum::response::sse::KeepAlive::new()
            .interval(heartbeat_interval)
            .text("ping"),
    );

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
        let dt = chrono::DateTime::parse_from_rfc3339(ts)
            .ok()?
            .with_timezone(&chrono::Utc);
        let uuid = Uuid::parse_str(id).ok()?;
        Some((dt, uuid))
    });
    let rows = repo::list_saved_posts(&s.db, me.id, cursor_pair, limit).await?;
    let next = if rows.len() as i64 == limit {
        rows.last()
            .map(|r| format!("{}|{}", r.saved_at.to_rfc3339(), r.id))
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
