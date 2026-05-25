use axum::{
    extract::{Request, State},
    http::header::COOKIE,
    middleware::Next,
    response::Response,
};
use std::sync::Arc;

use crate::{auth::verify_access, error::AppError, models::AuthUser};

#[derive(Clone)]
pub struct AuthState {
    pub jwt_secret: Arc<Vec<u8>>,
}

pub async fn require_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let token = extract_access_cookie(&req).ok_or(AppError::Unauthorized)?;
    let claims = verify_access(&state.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
    req.extensions_mut().insert(AuthUser {
        id: claims.sub,
        role: claims.role,
    });
    Ok(next.run(req).await)
}

pub async fn optional_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Response {
    if let Some(token) = extract_access_cookie(&req) {
        if let Ok(claims) = verify_access(&state.jwt_secret, &token) {
            req.extensions_mut().insert(AuthUser {
                id: claims.sub,
                role: claims.role,
            });
        }
    }
    next.run(req).await
}

fn extract_access_cookie(req: &Request) -> Option<String> {
    let raw = req.headers().get(COOKIE)?.to_str().ok()?;
    for kv in raw.split(';') {
        let kv = kv.trim();
        if let Some(rest) = kv.strip_prefix("oec_access=") {
            return Some(rest.to_string());
        }
    }
    None
}
