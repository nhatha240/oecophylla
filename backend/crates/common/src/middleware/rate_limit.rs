use axum::{extract::{Request, State}, middleware::Next, response::Response};
use deadpool_redis::Pool;
use redis::AsyncCommands;

use crate::error::AppError;

#[derive(Clone)]
pub struct RateLimitState {
    pub redis: Pool,
    pub limit_public: u32,
    pub limit_authed: u32,
}

pub async fn ip_rate_limit(
    State(state): State<RateLimitState>,
    req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let ip = req.headers().get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or("").trim().to_string())
        .unwrap_or_else(|| "unknown".into());
    let minute = chrono::Utc::now().timestamp() / 60;
    let key = format!("rate:ip:{ip}:{minute}");
    let mut conn = state.redis.get().await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    let n: i64 = conn.incr(&key, 1).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    if n == 1 {
        let _: () = conn.expire(&key, 65).await.map_err(|e| AppError::Other(anyhow::anyhow!(e)))?;
    }
    if (n as u32) > state.limit_public {
        return Err(AppError::RateLimited { retry_after_s: 60 });
    }
    Ok(next.run(req).await)
}
