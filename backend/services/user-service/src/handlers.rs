use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use common::{
    auth::verify_access,
    error::{AppError, AppResult},
    events::{Envelope, UserFollowed, TOPIC_USER_FOLLOWED},
};
use serde::Deserialize;
use uuid::Uuid;

use crate::{repo, state::AppState};

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
    let prefs_ref: Option<&[String]> = body.topic_prefs.as_deref();
    let row = repo::update_profile(
        &s.db,
        id,
        body.display_name.as_deref(),
        body.bio.as_deref(),
        body.avatar_url.as_deref(),
        prefs_ref,
    )
    .await?;
    Ok(Json(row))
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
