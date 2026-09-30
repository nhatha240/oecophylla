use axum::{
    extract::{Request, State},
    http::{header::COOKIE, HeaderMap},
    middleware::Next,
    response::Response,
};
use sqlx::PgPool;
use std::sync::Arc;

use crate::{
    auth::verify_access,
    error::AppError,
    models::{AuthUser, UserRole},
};

#[derive(Clone)]
pub struct AuthState {
    pub jwt_secret: Arc<Vec<u8>>,
    pub db: Option<PgPool>,
}

/// Resolve the active account and current role for a signed access cookie.
/// Role changes and account bans take effect without waiting for JWT expiry.
pub async fn current_active_user(
    db: &PgPool,
    jwt_secret: &[u8],
    headers: &HeaderMap,
) -> Result<Option<AuthUser>, AppError> {
    let token = headers
        .get(COOKIE)
        .and_then(|value| value.to_str().ok())
        .and_then(|raw| {
            raw.split(';')
                .find_map(|part| part.trim().strip_prefix("oec_access="))
        });
    let Some(claims) = token.and_then(|token| verify_access(jwt_secret, token).ok()) else {
        return Ok(None);
    };
    let role: Option<UserRole> =
        sqlx::query_scalar("SELECT role FROM users WHERE id = $1 AND is_active = true")
            .bind(claims.sub)
            .fetch_optional(db)
            .await?;
    Ok(role.map(|role| AuthUser {
        id: claims.sub,
        // A newly promoted account receives admin permissions on its next login.
        role: if claims.role == role {
            role
        } else {
            UserRole::User
        },
    }))
}

pub async fn require_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let user = if let Some(db) = &state.db {
        current_active_user(db, &state.jwt_secret, req.headers())
            .await?
            .ok_or(AppError::Unauthorized)?
    } else {
        let token = extract_access_cookie(&req).ok_or(AppError::Unauthorized)?;
        let claims =
            verify_access(&state.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
        AuthUser {
            id: claims.sub,
            role: claims.role,
        }
    };
    req.extensions_mut().insert(user);
    Ok(next.run(req).await)
}

/// Same gate as `require_auth` but additionally rejects non-admin accounts with 403.
pub async fn require_admin(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let user = if let Some(db) = &state.db {
        current_active_user(db, &state.jwt_secret, req.headers())
            .await?
            .ok_or(AppError::Unauthorized)?
    } else {
        let token = extract_access_cookie(&req).ok_or(AppError::Unauthorized)?;
        let claims =
            verify_access(&state.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
        AuthUser {
            id: claims.sub,
            role: claims.role,
        }
    };
    if user.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
    req.extensions_mut().insert(user);
    Ok(next.run(req).await)
}

pub async fn optional_auth(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Response {
    if let Some(db) = &state.db {
        if let Ok(Some(user)) = current_active_user(db, &state.jwt_secret, req.headers()).await {
            req.extensions_mut().insert(user);
        }
    } else if let Some(token) = extract_access_cookie(&req) {
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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{
        body::Body,
        http::{Request as HttpRequest, StatusCode},
        middleware::from_fn_with_state,
        response::IntoResponse,
        routing::get,
        Router,
    };
    use tower::ServiceExt;
    use uuid::Uuid;

    use crate::auth::issue_access;

    async fn ok_handler() -> impl IntoResponse {
        StatusCode::OK
    }

    fn make_state() -> AuthState {
        AuthState {
            jwt_secret: Arc::new(b"unit-test-secret".to_vec()),
            db: None,
        }
    }

    fn app(state: AuthState) -> Router {
        Router::new()
            .route("/protected", get(ok_handler))
            .layer(from_fn_with_state(state, require_admin))
    }

    fn token(secret: &[u8], role: UserRole) -> String {
        issue_access(secret, 60, Uuid::now_v7(), role).expect("issue access token")
    }

    #[tokio::test]
    async fn require_admin_allows_admin() {
        let state = make_state();
        let secret = state.jwt_secret.clone();
        let app = app(state);

        let tok = token(&secret, UserRole::Admin);
        let req = HttpRequest::builder()
            .uri("/protected")
            .header("cookie", format!("oec_access={tok}"))
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn require_admin_rejects_user_with_403() {
        let state = make_state();
        let secret = state.jwt_secret.clone();
        let app = app(state);

        let tok = token(&secret, UserRole::User);
        let req = HttpRequest::builder()
            .uri("/protected")
            .header("cookie", format!("oec_access={tok}"))
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn require_admin_rejects_creator_with_403() {
        let state = make_state();
        let secret = state.jwt_secret.clone();
        let app = app(state);

        let tok = token(&secret, UserRole::Creator);
        let req = HttpRequest::builder()
            .uri("/protected")
            .header("cookie", format!("oec_access={tok}"))
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn require_admin_rejects_missing_cookie_with_401() {
        let state = make_state();
        let app = app(state);

        let req = HttpRequest::builder()
            .uri("/protected")
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }
}
