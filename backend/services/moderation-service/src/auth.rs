use axum::{
    extract::{Request, State},
    http::header::COOKIE,
    middleware::Next,
    response::Response,
};
use common::{
    auth::verify_access,
    error::AppError,
    models::{AuthUser, UserRole},
};
use sqlx::PgPool;

#[derive(Clone)]
pub struct AdminAuthState {
    pub db: PgPool,
    pub jwt_secret: Vec<u8>,
}

pub async fn require_current_admin(
    State(state): State<AdminAuthState>,
    mut request: Request,
    next: Next,
) -> Result<Response, AppError> {
    let cookie = request
        .headers()
        .get(COOKIE)
        .and_then(|value| value.to_str().ok())
        .ok_or(AppError::Unauthorized)?;
    let token = cookie
        .split(';')
        .find_map(|part| part.trim().strip_prefix("oec_access="))
        .ok_or(AppError::Unauthorized)?;
    let claims = verify_access(&state.jwt_secret, token).map_err(|_| AppError::Unauthorized)?;
    if claims.role != UserRole::Admin {
        return Err(AppError::Forbidden);
    }

    // The JWT may outlive a role change or account ban. Check the current row
    // before every moderation request so a demoted admin loses access at once.
    let active_admin: Option<bool> =
        sqlx::query_scalar("SELECT role::text = 'admin' AND is_active FROM users WHERE id = $1")
            .bind(claims.sub)
            .fetch_optional(&state.db)
            .await?;
    if active_admin != Some(true) {
        return Err(AppError::Forbidden);
    }

    request.extensions_mut().insert(AuthUser {
        id: claims.sub,
        role: UserRole::Admin,
    });
    Ok(next.run(request).await)
}
