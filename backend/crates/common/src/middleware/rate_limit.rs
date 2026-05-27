use std::sync::Arc;

use axum::{
    extract::{Request, State},
    http::header::COOKIE,
    middleware::Next,
    response::Response,
};
use deadpool_redis::{redis::AsyncCommands, Pool};

use crate::{auth::verify_access, error::AppError, models::AuthUser};

#[derive(Clone, Debug)]
pub struct RateLimitPolicy {
    pub key_prefix: &'static str,
    pub max_per_minute: u32,
}

impl RateLimitPolicy {
    /// Build a policy, allowing the per-bucket env var
    /// `RATE_LIMIT_<KEY_PREFIX_UPPER>` to override `default_max_per_minute`
    /// at startup. Used by smoke tests to lower a bucket without recompiling.
    pub fn new(key_prefix: &'static str, default_max_per_minute: u32) -> Self {
        let env_key = format!(
            "RATE_LIMIT_{}",
            key_prefix.to_uppercase().replace('-', "_")
        );
        let max_per_minute = std::env::var(&env_key)
            .ok()
            .and_then(|v| v.parse::<u32>().ok())
            .filter(|n| *n > 0)
            .unwrap_or(default_max_per_minute);
        Self {
            key_prefix,
            max_per_minute,
        }
    }
}

#[derive(Clone)]
pub struct RateLimitState {
    pub redis: Pool,
    pub policy: RateLimitPolicy,
    pub jwt_secret: Arc<Vec<u8>>,
}

/// Per-minute sliding-window limit keyed by authenticated user when an
/// `oec_access` cookie is present, otherwise by client IP.
pub async fn enforce_rate_limit(
    State(state): State<RateLimitState>,
    req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let ident = if let Some(user) = req.extensions().get::<AuthUser>() {
        format!("u:{}", user.id)
    } else if let Some(token) = extract_access_cookie(&req) {
        match verify_access(&state.jwt_secret, &token) {
            Ok(claims) => format!("u:{}", claims.sub),
            Err(_) => format!("ip:{}", client_ip(&req)),
        }
    } else {
        format!("ip:{}", client_ip(&req))
    };

    let minute = chrono::Utc::now().timestamp() / 60;
    let key = format!("rate:{}:{}:{}", state.policy.key_prefix, ident, minute);

    let mut conn = state
        .redis
        .get()
        .await
        .map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let count: i64 = conn
        .incr(&key, 1)
        .await
        .map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    if count == 1 {
        let _: () = conn
            .expire(&key, 65)
            .await
            .map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    }
    if (count as u32) > state.policy.max_per_minute {
        return Err(AppError::RateLimited { retry_after_s: 60 });
    }
    Ok(next.run(req).await)
}

fn client_ip(req: &Request) -> String {
    req.headers()
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.split(',').next().map(|s| s.trim().to_string()))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".into())
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
