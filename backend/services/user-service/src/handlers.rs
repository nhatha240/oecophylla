use axum::{
    body::Body,
    extract::{Multipart, Path, Query, State},
    http::{header, HeaderValue, Response, StatusCode},
    response::IntoResponse,
    Json,
};
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    events::{Envelope, UserFollowed, TOPIC_USER_FOLLOWED},
};
use deadpool_redis::redis::AsyncCommands;
use serde::Deserialize;
use std::collections::HashSet;
use uuid::Uuid;

use crate::{
    avatar::{validate_avatar_upload, validate_avatar_url, MAX_AVATAR_BYTES},
    repo,
    state::AppState,
};

#[derive(Deserialize)]
pub struct UpdateProfileReq {
    pub display_name: Option<String>,
    pub bio: Option<String>,
    pub avatar_url: Option<String>,
    pub topic_prefs: Option<Vec<String>>,
}

#[derive(Deserialize)]
pub struct PageQ {
    pub limit: Option<i64>,
}

#[derive(Deserialize)]
pub struct SearchQ {
    pub q: Option<String>,
    #[serde(rename = "type")]
    pub _search_type: Option<String>,
    pub page: Option<i64>,
    pub limit: Option<i64>,
}

#[derive(Deserialize)]
pub struct SuggestionsQ {
    pub limit: Option<i64>,
}

#[derive(serde::Serialize)]
pub struct AvatarUploadResponse {
    pub avatar_url: String,
}

#[derive(serde::Serialize)]
pub struct UserSearchResponse {
    pub items: Vec<repo::ProfileRow>,
    pub total: Option<i64>,
    pub page: i64,
}

fn current_user(s: &AppState, h: &axum::http::HeaderMap) -> Option<common::models::AuthUser> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    let token = raw
        .split(';')
        .find_map(|kv| kv.trim().strip_prefix("oec_access=").map(String::from))?;
    let c = verify_access(s.cfg.jwt_secret.as_bytes(), &token).ok()?;
    Some(common::models::AuthUser {
        id: c.sub,
        role: c.role,
    })
}

fn topic_preferences_changed(before: &[String], after: &[String]) -> bool {
    let before: HashSet<&str> = before.iter().map(String::as_str).collect();
    let after: HashSet<&str> = after.iter().map(String::as_str).collect();
    before != after
}

async fn invalidate_topic_preference_caches(s: &AppState, user_id: Uuid) {
    let result = async {
        let mut conn = s.redis.get().await.map_err(|err| err.to_string())?;
        let keys = preference_cache_keys(user_id);
        let deleted: usize = conn.del(&keys).await.map_err(|err| err.to_string())?;
        Ok::<usize, String>(deleted)
    }
    .await;

    match result {
        Ok(deleted) => {
            metrics::counter!("user_topic_cache_invalidation_total", "result" => "success")
                .increment(1);
            tracing::info!(deleted, "invalidated topic preference caches");
        }
        Err(error) => {
            metrics::counter!("user_topic_cache_invalidation_total", "result" => "error")
                .increment(1);
            tracing::warn!(%error, "failed to invalidate topic preference caches");
        }
    }
}

pub async fn get(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
) -> AppResult<Json<repo::ProfileResponse>> {
    let viewer = current_user(&s, &h);
    match viewer {
        Some(me) => repo::get_profile_with_following(&s.db, id, me.id)
            .await?
            .map(Json)
            .ok_or(AppError::NotFound {
                kind: "user".into(),
            }),
        None => repo::get_profile(&s.db, id)
            .await?
            .map(|profile| {
                Json(repo::ProfileResponse {
                    profile,
                    is_following: false,
                })
            })
            .ok_or(AppError::NotFound {
                kind: "user".into(),
            }),
    }
}

pub async fn update(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
    Json(body): Json<UpdateProfileReq>,
) -> AppResult<Json<repo::ProfileRow>> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    if me.id != id {
        return Err(AppError::Forbidden);
    }
    let previous_profile = if body.avatar_url.is_some() || body.topic_prefs.is_some() {
        repo::get_profile(&s.db, id).await?
    } else {
        None
    };
    if let Some(avatar_url) = body.avatar_url.as_deref() {
        // Settings sends the current avatar with every profile save. Preserve
        // this user's stored upload URL without accepting arbitrary local URLs.
        let is_stored_upload = avatar_url.starts_with(&format!("/api/v1/users/{id}/avatar?v="))
            && previous_profile
                .as_ref()
                .and_then(|profile| profile.avatar_url.as_deref())
                == Some(avatar_url);
        if !is_stored_upload {
            validate_avatar_url(avatar_url)?;
        }
    }
    let prefs_ref: Option<&[String]> = body.topic_prefs.as_deref();
    let previous_topic_prefs = previous_profile.map(|profile| profile.topic_prefs);
    let row = repo::update_profile(
        &s.db,
        id,
        body.display_name.as_deref(),
        body.bio.as_deref(),
        body.avatar_url.as_deref(),
        prefs_ref,
    )
    .await?;
    if previous_topic_prefs
        .as_deref()
        .is_some_and(|before| topic_preferences_changed(before, &row.topic_prefs))
    {
        // The profile update remains successful if Redis is temporarily down.
        // The short-lived stale cache is observable and will expire normally.
        invalidate_topic_preference_caches(&s, id).await;
    }
    Ok(Json(row))
}

fn preference_cache_keys(user_id: Uuid) -> Vec<String> {
    [
        "pref:",
        "pref:v1:",
        "pref:v2:",
        "history:v1:",
        "history:v2:",
        "feed:",
        "feed:v1:",
        "feed:v2:",
    ]
    .iter()
    .map(|prefix| format!("{prefix}{user_id}"))
    .collect()
}

pub async fn upload_avatar(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
    mut multipart: Multipart,
) -> AppResult<Json<AvatarUploadResponse>> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    if me.id != id {
        return Err(AppError::Forbidden);
    }

    let mut avatar = None;
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|_| AppError::Validation {
            field: "avatar".into(),
            message: "invalid multipart upload".into(),
        })?
    {
        if field.name() != Some("avatar") {
            continue;
        }
        if avatar.is_some() {
            return Err(AppError::Validation {
                field: "avatar".into(),
                message: "upload exactly one avatar file".into(),
            });
        }
        let filename = field.file_name().unwrap_or_default().to_owned();
        let declared_content_type = field.content_type().unwrap_or_default().to_owned();
        let bytes = field.bytes().await.map_err(|_| AppError::Validation {
            field: "avatar".into(),
            message: "could not read avatar upload".into(),
        })?;
        let format = validate_avatar_upload(&declared_content_type, &filename, &bytes)?;
        avatar = Some((format, bytes));
    }

    let (format, bytes) = avatar.ok_or(AppError::Validation {
        field: "avatar".into(),
        message: "avatar file is required".into(),
    })?;
    debug_assert!(bytes.len() <= MAX_AVATAR_BYTES);
    let avatar_url = repo::upsert_avatar(&s.db, id, format.content_type(), &bytes).await?;
    Ok(Json(AvatarUploadResponse { avatar_url }))
}

pub async fn avatar(State(s): State<AppState>, Path(id): Path<Uuid>) -> AppResult<Response<Body>> {
    let avatar = repo::get_avatar(&s.db, id)
        .await?
        .ok_or(AppError::NotFound {
            kind: "avatar".into(),
        })?;
    let content_type = HeaderValue::from_str(&avatar.content_type)
        .map_err(|error| AppError::Other(error.into()))?;
    let mut response = Response::new(Body::from(avatar.image_data));
    response
        .headers_mut()
        .insert(header::CONTENT_TYPE, content_type);
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        HeaderValue::from_static("public, max-age=31536000, immutable"),
    );
    response.headers_mut().insert(
        header::X_CONTENT_TYPE_OPTIONS,
        HeaderValue::from_static("nosniff"),
    );
    Ok(response)
}

pub async fn follow(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
) -> AppResult<impl IntoResponse> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    if me.id == id {
        return Err(AppError::Validation {
            field: "id".into(),
            message: "cannot follow self".into(),
        });
    }
    let created = repo::insert_follow(&s.db, me.id, id).await?;
    if created {
        let env = Envelope::new(
            "user.followed",
            "user-service",
            UserFollowed {
                follower_id: me.id,
                followee_id: id,
                followed_at: common::time::now(),
            },
        );
        s.kafka
            .produce_json(TOPIC_USER_FOLLOWED, id.to_string().as_str(), &env)
            .await;
    }
    Ok(StatusCode::CREATED)
}

pub async fn unfollow(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    h: axum::http::HeaderMap,
) -> AppResult<impl IntoResponse> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    repo::delete_follow(&s.db, me.id, id).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn followers(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    Query(q): Query<PageQ>,
) -> AppResult<Json<Vec<repo::ProfileRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_followers(&s.db, id, limit).await?))
}

pub async fn following(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
    Query(q): Query<PageQ>,
) -> AppResult<Json<Vec<repo::ProfileRow>>> {
    let limit = q.limit.unwrap_or(20).clamp(1, 100);
    Ok(Json(repo::list_following(&s.db, id, limit).await?))
}

pub async fn search_users(
    State(s): State<AppState>,
    Query(q): Query<SearchQ>,
) -> AppResult<Json<UserSearchResponse>> {
    let q_str = q.q.unwrap_or_default();
    let page = q.page.unwrap_or(0).max(0);
    if q_str.trim().len() < 2 {
        return Ok(Json(UserSearchResponse {
            items: vec![],
            total: Some(0),
            page,
        }));
    }
    let limit = q.limit.unwrap_or(20).clamp(1, 50);
    let (items, total) = repo::search_users(&s.db, q_str.trim(), limit, page).await?;
    Ok(Json(UserSearchResponse {
        items,
        total: Some(total),
        page,
    }))
}

pub async fn get_preferences(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<Json<repo::UserPreferenceRow>> {
    repo::get_user_preferences(&s.db, id)
        .await?
        .map(Json)
        .ok_or(AppError::NotFound {
            kind: "preferences".into(),
        })
}

pub async fn suggestions(
    State(s): State<AppState>,
    h: axum::http::HeaderMap,
    Query(q): Query<SuggestionsQ>,
) -> AppResult<Json<Vec<repo::SuggestionRow>>> {
    let me = current_user(&s, &h).ok_or(AppError::Unauthorized)?;
    let limit = q.limit.unwrap_or(10).clamp(1, 50);
    let items = repo::get_suggestions(&s.db, me.id, limit).await?;
    if items.is_empty() {
        let fallback = repo::fallback_suggestions(&s.db, me.id, limit).await?;
        return Ok(Json(fallback));
    }
    Ok(Json(items))
}

#[cfg(test)]
mod tests {
    use super::{preference_cache_keys, topic_preferences_changed};
    use uuid::Uuid;

    #[test]
    fn declared_topic_change_invalidates_all_preference_history_and_feed_versions() {
        assert_eq!(
            preference_cache_keys(Uuid::nil()),
            vec![
                "pref:00000000-0000-0000-0000-000000000000",
                "pref:v1:00000000-0000-0000-0000-000000000000",
                "pref:v2:00000000-0000-0000-0000-000000000000",
                "history:v1:00000000-0000-0000-0000-000000000000",
                "history:v2:00000000-0000-0000-0000-000000000000",
                "feed:00000000-0000-0000-0000-000000000000",
                "feed:v1:00000000-0000-0000-0000-000000000000",
                "feed:v2:00000000-0000-0000-0000-000000000000",
            ]
        );
    }

    #[test]
    fn topic_change_comparison_ignores_order_and_duplicates() {
        assert!(!topic_preferences_changed(
            &["tech".into(), "sports".into()],
            &["sports".into(), "tech".into(), "tech".into()],
        ));
    }

    #[test]
    fn topic_change_comparison_detects_semantic_changes() {
        assert!(topic_preferences_changed(
            &["tech".into()],
            &["science".into()],
        ));
    }
}
