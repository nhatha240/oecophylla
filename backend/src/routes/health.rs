use axum::extract::State;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::json;
use sqlx::Executor;

use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new().route("/health", get(health))
}

async fn health(State(state): State<AppState>) -> impl IntoResponse {
    match state.pool.execute("SELECT 1").await {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "status": "ok", "db": "ok" })),
        ),
        Err(err) => {
            tracing::warn!(error = ?err, "health check db ping failed");
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "status": "degraded", "db": "down" })),
            )
        }
    }
}
