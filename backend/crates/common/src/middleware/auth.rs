use axum::{
    extract::{Request, State},
    http::header::COOKIE,
    middleware::Next,
    response::Response,
};
use std::sync::Arc;

use crate::{
    auth::verify_access,
    error::AppError,
    models::{AuthUser, UserRole},
};

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

/// Same gate as `require_auth` but additionally rejects non-admin tokens with 403.
/// All `/admin/*` routes in moderation-service use this.
pub async fn require_admin(
    State(state): State<AuthState>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let token = extract_access_cookie(&req).ok_or(AppError::Unauthorized)?;
    let claims = verify_access(&state.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
    if claims.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }
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
