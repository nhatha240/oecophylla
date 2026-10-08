use axum::{
    body::Body,
    extract::{Multipart, Path, Query, State},
    http::{header, HeaderValue, Response, StatusCode},
    response::IntoResponse,
    Json,
};
use common::{
    error::{AppError, AppResult},
    events::{ContentCreated, Envelope, TOPIC_CONTENT_CREATED},
    middleware::auth::current_active_user,
    models::{AuthUser, PostStatus, UserRole},
};
use serde::Deserialize;
use std::future::Future;
use uuid::Uuid;

use crate::{
    cursor,
    image::validate_post_image,
    repo,
    state::AppState,
    update::{validate_owned_uploads, validate_update_post, UpdatePostInput},
};

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

#[derive(serde::Serialize)]
pub struct ImageUploadResponse {
    pub image_url: String,
}

pub async fn upload_image(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
    mut multipart: Multipart,
) -> AppResult<Json<ImageUploadResponse>> {
    let me = current(&s, &h).await?.ok_or(AppError::Unauthorized)?;
    let post = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    if post.author_id != me.id && me.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    let mut image = None;
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|_| AppError::Validation {
            field: "image".into(),
            message: "invalid multipart upload".into(),
        })?
    {
        if field.name() != Some("image") {
            continue;
        }
        if image.is_some() {
            return Err(AppError::Validation {
                field: "image".into(),
                message: "upload exactly one image".into(),
            });
        }
        let filename = field.file_name().unwrap_or_default().to_owned();
        let content_type = field.content_type().unwrap_or_default().to_owned();
        let bytes = field.bytes().await.map_err(|_| AppError::Validation {
            field: "image".into(),
            message: "could not read image upload".into(),
        })?;
        let format = validate_post_image(&content_type, &filename, &bytes)?;
        image = Some((format, bytes));
    }
    let (format, bytes) = image.ok_or(AppError::Validation {
        field: "image".into(),
        message: "image file is required".into(),
    })?;
    let image_url = repo::insert_image(&s.db, id, format, &bytes).await?;
    publish_image_change(&s, id).await?;
    Ok(Json(ImageUploadResponse { image_url }))
}

async fn publish_image_change(s: &AppState, id: Uuid) -> AppResult<()> {
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    let env = Envelope::new(
        "content.updated",
        "content-service",
        ContentCreated {
            post_id: row.id,
            author_id: row.author_id,
            content: row.content,
            tags: row.tags,
            created_at: row.updated_at,
        },
    );
    s.kafka
        .produce_json(TOPIC_CONTENT_CREATED, id.to_string().as_str(), &env)
        .await;
    Ok(())
}

pub async fn image(
    State(s): State<AppState>,
    Path((id, image_id)): Path<(Uuid, Uuid)>,
    h: axum::http::HeaderMap,
) -> AppResult<Response<Body>> {
    let post = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "image".into(),
    })?;
    let image_url = format!("/api/v1/posts/{id}/images/{image_id}");
    if !post.media_urls.contains(&image_url)
        || (post.status != PostStatus::Published
            && !current(&s, &h).await?.is_some_and(|viewer| {
                viewer.id == post.author_id || viewer.role == UserRole::Admin
            }))
    {
        return Err(AppError::NotFound {
            kind: "image".into(),
        });
    }
    let image = repo::get_image(&s.db, id, image_id)
        .await?
        .ok_or(AppError::NotFound {
            kind: "image".into(),
        })?;
    let content_type = HeaderValue::from_str(&image.content_type)
        .map_err(|error| AppError::Other(error.into()))?;
    let mut response = Response::new(Body::from(image.image_data));
    response
        .headers_mut()
        .insert(header::CONTENT_TYPE, content_type);
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        HeaderValue::from_static("private, no-store"),
    );
    response.headers_mut().insert(
        header::X_CONTENT_TYPE_OPTIONS,
        HeaderValue::from_static("nosniff"),
    );
    Ok(response)
}

pub async fn delete_image(
    State(s): State<AppState>,
    Path((id, image_id)): Path<(Uuid, Uuid)>,
    h: axum::http::HeaderMap,
) -> AppResult<StatusCode> {
    let me = current(&s, &h).await?.ok_or(AppError::Unauthorized)?;
    let post = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    if post.author_id != me.id && me.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    repo::delete_image(&s.db, id, image_id).await?;
    publish_image_change(&s, id).await?;
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Deserialize)]
pub struct ListQ {
    pub author_id: Option<Uuid>,
    pub tag: Option<String>,
    pub topic: Option<String>,
    pub cursor: Option<String>,
    pub limit: Option<i64>,
}

async fn current(s: &AppState, h: &axum::http::HeaderMap) -> AppResult<Option<AuthUser>> {
    current_active_user(&s.db, s.cfg.jwt_secret.as_bytes(), h).await
}

pub async fn create(
    State(s): State<AppState>,
    h: axum::http::HeaderMap,
    Json(body): Json<CreatePostReq>,
) -> AppResult<Json<repo::PostRow>> {
    let me = current(&s, &h).await?.ok_or(AppError::Unauthorized)?;
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
    let post_topics = body.topics.clone();
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
    h: axum::http::HeaderMap,
) -> AppResult<Json<repo::PostRow>> {
    let row = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    // A direct URL must enforce the same publication boundary as public lists.
    // Authors and administrators can still inspect content awaiting moderation.
    if row.status != PostStatus::Published
        && !current(&s, &h)
            .await?
            .is_some_and(|viewer| viewer.id == row.author_id || viewer.role == UserRole::Admin)
    {
        return Err(AppError::NotFound {
            kind: "post".into(),
        });
    }
    Ok(Json(row))
}

pub async fn update_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
    Json(body): Json<UpdatePostInput>,
) -> AppResult<Json<repo::PostRow>> {
    let me = current(&s, &h).await?.ok_or(AppError::Unauthorized)?;
    let existing = repo::by_id(&s.db, id).await?.ok_or(AppError::NotFound {
        kind: "post".into(),
    })?;
    if existing.author_id != me.id && me.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    let body = validate_update_post(body)?;
    validate_owned_uploads(body.media_urls.as_deref(), &existing.media_urls)?;
    let row = repo::update(
        &s.db,
        id,
        body.content.as_deref(),
        body.media_urls.as_deref(),
        body.tags.as_deref(),
        body.topics.as_deref(),
    )
    .await?;

    let env = Envelope::new(
        "content.updated",
        "content-service",
        ContentCreated {
            post_id: row.id,
            author_id: row.author_id,
            content: row.content.clone(),
            tags: row.tags.clone(),
            created_at: row.updated_at,
        },
    );
    s.kafka
        .produce_json(TOPIC_CONTENT_CREATED, row.id.to_string().as_str(), &env)
        .await;
    Ok(Json(row))
}

#[derive(serde::Serialize)]
pub struct ListResponse {
    pub items: Vec<repo::PostRow>,
    pub next_cursor: Option<String>,
}

pub async fn list(
    State(s): State<AppState>,
    Query(q): Query<ListQ>,
) -> AppResult<Json<ListResponse>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let cursor_pair = q.cursor.as_deref().and_then(cursor::decode);

    if let Some(ref tag) = q.tag {
        let rows = repo::list_by_tag(&s.db, tag, cursor_pair, limit).await?;
        let next = if rows.len() as i64 == limit {
            rows.last().map(|r| cursor::encode(r.created_at, r.id))
        } else {
            None
        };
        return Ok(Json(ListResponse {
            items: rows,
            next_cursor: next,
        }));
    }

    if let Some(ref topic) = q.topic {
        let rows = repo::list_by_topic(&s.db, topic, cursor_pair, limit).await?;
        let next = if rows.len() as i64 == limit {
            rows.last().map(|r| cursor::encode(r.created_at, r.id))
        } else {
            None
        };
        return Ok(Json(ListResponse {
            items: rows,
            next_cursor: next,
        }));
    }

    let author = q.author_id.ok_or(AppError::Validation {
        field: "author_id".into(),
        message: "required when no tag or topic filter".into(),
    })?;
    let rows = repo::list_by_author(&s.db, author, limit).await?;
    Ok(Json(ListResponse {
        items: rows,
        next_cursor: None,
    }))
}

pub async fn delete_post(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
) -> AppResult<impl IntoResponse> {
    let me = current(&s, &h).await?.ok_or(AppError::Unauthorized)?;
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
    maybe_increment_legacy_view(s.legacy_view_counter_enabled, || {
        repo::increment_legacy_view(&s.db, id)
    })
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

async fn maybe_increment_legacy_view<F, Fut>(enabled: bool, increment: F) -> AppResult<()>
where
    F: FnOnce() -> Fut,
    Fut: Future<Output = AppResult<()>>,
{
    if enabled {
        increment().await?;
    }
    Ok(())
}

// --- GET /api/v1/search ---

#[derive(Deserialize)]
pub struct SearchQ {
    pub q: Option<String>,
    #[serde(rename = "type")]
    pub type_: Option<String>,
    pub cursor: Option<String>,
    pub limit: Option<i64>,
}

#[derive(serde::Serialize)]
pub struct SearchResponse {
    pub items: Vec<repo::SearchPostRow>,
    pub next_cursor: Option<String>,
}

pub async fn search(
    State(s): State<AppState>,
    Query(q): Query<SearchQ>,
) -> AppResult<Json<SearchResponse>> {
    let query = match q.q.as_deref() {
        Some(q) if q.trim().len() >= 2 => q.trim(),
        _ => {
            return Ok(Json(SearchResponse {
                items: vec![],
                next_cursor: None,
            }))
        }
    };

    let type_ = q.type_.as_deref().unwrap_or("post");
    if type_ != "post" {
        return Ok(Json(SearchResponse {
            items: vec![],
            next_cursor: None,
        }));
    }

    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    let cursor_pair = q.cursor.as_deref().and_then(cursor::decode);
    let (cursor_ts, cursor_id) = match cursor_pair {
        Some((ts, id)) => (Some(ts), Some(id)),
        None => (None, None),
    };

    let rows = repo::search_posts(&s.db, query, limit, cursor_ts, cursor_id).await?;
    let next = if rows.len() as i64 == limit {
        rows.last().map(|r| cursor::encode(r.created_at, r.id))
    } else {
        None
    };

    Ok(Json(SearchResponse {
        items: rows,
        next_cursor: next,
    }))
}

#[cfg(test)]
mod tests {
    use super::maybe_increment_legacy_view;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    };

    #[tokio::test]
    async fn disabled_legacy_counter_is_a_successful_noop() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed = calls.clone();

        maybe_increment_legacy_view(false, || async move {
            observed.fetch_add(1, Ordering::SeqCst);
            Ok(())
        })
        .await
        .unwrap();

        assert_eq!(calls.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn enabled_legacy_counter_preserves_the_single_increment() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed = calls.clone();

        maybe_increment_legacy_view(true, || async move {
            observed.fetch_add(1, Ordering::SeqCst);
            Ok(())
        })
        .await
        .unwrap();

        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }
}
