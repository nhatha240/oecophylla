use axum::{extract::State, http::{header::{HeaderMap, SET_COOKIE}, StatusCode}, response::{IntoResponse, Response}, Json};
use common::{auth::*, error::{AppError, AppResult}, models::UserRole};
use deadpool_redis::redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use validator::Validate;

use crate::{state::AppState, repo};

static USERNAME_RE: once_cell::sync::Lazy<regex::Regex> =
    once_cell::sync::Lazy::new(|| regex::Regex::new(r"^[a-z0-9_]{3,30}$").unwrap());

#[derive(Deserialize, Validate)]
pub struct RegisterReq {
    #[validate(regex(path = "*USERNAME_RE", message = "username must be 3-30 chars, a-z0-9_"))]
    pub username: String,
    #[validate(email)]
    pub email: String,
    #[validate(length(min = 8, max = 128))]
    pub password: String,
    pub display_name: Option<String>,
}

#[derive(Deserialize)]
pub struct LoginReq { pub email_or_username: String, pub password: String }

#[derive(Serialize)]
pub struct UserDto { pub id: Uuid, pub username: String, pub email: String, pub role: UserRole, pub display_name: Option<String>, pub avatar_url: Option<String> }
#[derive(Serialize)]
pub struct AuthBody { pub user: UserDto }

fn dto(u: repo::UserRow) -> UserDto {
    UserDto { id: u.id, username: u.username, email: u.email, role: u.role, display_name: u.display_name, avatar_url: u.avatar_url }
}

pub async fn register(State(s): State<AppState>, Json(body): Json<RegisterReq>) -> AppResult<Response> {
    body.validate().map_err(|e| AppError::Validation { field: "body".into(), message: e.to_string() })?;
    let hash = hash_password(&body.password, s.cfg.argon2_m_cost, s.cfg.argon2_t_cost, s.cfg.argon2_p_cost)
        .map_err(AppError::Other)?;
    let user = repo::insert_user(&s.db, &body.username, &body.email, &hash, body.display_name.as_deref()).await?;
    let response = build_auth_response(&s, &user).await?;
    Ok(response)
}

pub async fn login(State(s): State<AppState>, Json(body): Json<LoginReq>) -> AppResult<Response> {
    let user = repo::find_by_email_or_username(&s.db, &body.email_or_username).await?
        .ok_or(AppError::Unauthorized)?;
    if !verify_password(&body.password, &user.password_hash) {
        return Err(AppError::Unauthorized);
    }
    build_auth_response(&s, &user).await
}

pub async fn refresh(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    let token = extract_cookie(&headers, "oec_refresh").ok_or(AppError::Unauthorized)?;
    let hash = sha256_hex(&token);
    let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let key = format!("session:refresh:{hash}");
    let user_id: Option<String> = conn.get(&key).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let user_id: Uuid = user_id.ok_or(AppError::Unauthorized)?.parse().map_err(|_| AppError::Unauthorized)?;
    let _: () = conn.del(&key).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let user = repo::find_by_id(&s.db, user_id).await?.ok_or(AppError::Unauthorized)?;
    build_auth_response(&s, &user).await
}

pub async fn logout(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    if let Some(token) = extract_cookie(&headers, "oec_refresh") {
        let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
        let _: i64 = conn.del(format!("session:refresh:{}", sha256_hex(&token))).await
            .map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    }
    let mut resp = StatusCode::NO_CONTENT.into_response();
    resp.headers_mut().append(SET_COOKIE, clear_cookie_header("oec_access", "/"));
    resp.headers_mut().append(SET_COOKIE, clear_cookie_header("oec_refresh", "/api/v1/auth"));
    Ok(resp)
}

pub async fn me(State(s): State<AppState>, headers: HeaderMap) -> AppResult<Json<AuthBody>> {
    let token = extract_cookie(&headers, "oec_access").ok_or(AppError::Unauthorized)?;
    let claims = verify_access(s.cfg.jwt_secret.as_bytes(), &token).map_err(|_| AppError::Unauthorized)?;
    let user = repo::find_by_id(&s.db, claims.sub).await?.ok_or(AppError::Unauthorized)?;
    Ok(Json(AuthBody { user: dto(user) }))
}

async fn build_auth_response(s: &AppState, user: &repo::UserRow) -> AppResult<Response> {
    let access = issue_access(s.cfg.jwt_secret.as_bytes(), s.cfg.jwt_access_ttl_seconds, user.id, user.role)
        .map_err(AppError::Other)?;
    let (refresh_token, refresh_hash) = new_refresh_token();
    let mut conn = s.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let _: () = conn.set_ex(format!("session:refresh:{refresh_hash}"), user.id.to_string(), s.cfg.jwt_refresh_ttl_seconds as u64)
        .await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;

    let body = Json(AuthBody { user: dto(user.clone()) }).into_response();
    let (mut parts, body) = body.into_parts();
    parts.headers.append(SET_COOKIE, cookie_header(CookieOpts {
        name: "oec_access", value: access, path: "/", max_age_seconds: s.cfg.jwt_access_ttl_seconds, same_site: "Lax", secure: false }));
    parts.headers.append(SET_COOKIE, cookie_header(CookieOpts {
        name: "oec_refresh", value: refresh_token, path: "/api/v1/auth", max_age_seconds: s.cfg.jwt_refresh_ttl_seconds, same_site: "Strict", secure: false }));
    Ok(Response::from_parts(parts, body))
}

fn extract_cookie(h: &HeaderMap, name: &str) -> Option<String> {
    let raw = h.get(axum::http::header::COOKIE)?.to_str().ok()?;
    raw.split(';').find_map(|kv| {
        let kv = kv.trim();
        kv.strip_prefix(&format!("{name}="))
    }).map(String::from)
}
