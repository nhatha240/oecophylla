use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    events::{ContentCreated, Envelope, TOPIC_CONTENT_CREATED},
    models::{AuthUser, PostStatus, UserRole},
};
use serde::Deserialize;
use uuid::Uuid;

use crate::{repo, state::AppState, topics};

#[derive(Deserialize)]
pub struct CreatePostReq {
    pub content: String,
    #[serde(default)]
    pub media_urls: Vec<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub topics: Vec<String>,
}

#[derive(Deserialize)]
pub struct ListQ {
    pub author_id: Option<Uuid>,
    pub limit: Option<i64>,
}

fn current(s: &AppState, h: &axum::http::HeaderMap) -> Option<AuthUser> {
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

pub async fn create(
    State(s): State<AppState>,
    h: axum::http::HeaderMap,
    Json(body): Json<CreatePostReq>,
) -> AppResult<Json<repo::PostRow>> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let content = body.content.trim();
    if content.is_empty() || content.chars().count() > 4000 {
        return Err(AppError::Validation {
            field: "content".into(),
            message: "1..=4000 chars".into(),
        });
    }
    if body.media_urls.len() > 6
        || body
            .media_urls
            .iter()
            .any(|url| !url.starts_with("https://"))
    {
        return Err(AppError::Validation {
            field: "media_urls".into(),
            message: "<=6 https urls".into(),
        });
    }
    if body.tags.len() > 8 {
        return Err(AppError::Validation {
            field: "tags".into(),
            message: "<=8 tags".into(),
        });
    }

    let status = if s.cfg.auto_publish {
        PostStatus::Published
    } else {
        PostStatus::Pending
    };
    let post_topics = topics::infer_topics(content, &body.tags, &body.topics);
    let row = repo::insert(
        &s.db,
        me.id,
        content,
        &body.media_urls,
        &body.tags,
        &post_topics,
        status,
    )
    .await?;
    let env = Envelope::new(
        "content.created",
        "content-service",
        ContentCreated {
            post_id: row.id,
            author_id: row.author_id,
            content: row.content.clone(),
            tags: row.tags.clone(),
            created_at: row.created_at,
        },
    );
    s.kafka
        .produce_json(TOPIC_CONTENT_CREATED, row.id.to_string().as_str(), &env)
        .await;
    Ok(Json(row))
}

pub async fn get_one(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<Json<repo::PostRow>> {
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    Ok(Json(row))
}

pub async fn list(
    State(s): State<AppState>,
    Query(q): Query<ListQ>,
) -> AppResult<Json<Vec<repo::PostRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let author = q.author_id.ok_or(AppError::Validation {
        field: "author_id".into(),
        message: "required".into(),
    })?;
    Ok(Json(repo::list_by_author(&s.db, author, limit).await?))
}

pub async fn delete_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).ok_or(AppError::Unauthorized)?;
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    if row.author_id != me.id && me.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    repo::delete(&s.db, id).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn view(State(s): State<AppState>, Path(id): Path<Uuid>) -> AppResult<impl IntoResponse> {
    repo::increment_view(&s.db, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
