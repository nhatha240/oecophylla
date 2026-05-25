use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("validation failed: {field}: {message}")]
    Validation { field: String, message: String },
    #[error("unauthorized")]
    Unauthorized,
    #[error("forbidden")]
    Forbidden,
    #[error("not found: {kind}")]
    NotFound { kind: String },
    #[error("conflict: {kind}")]
    Conflict { kind: String },
    #[error("rate limited (retry in {retry_after_s}s)")]
    RateLimited { retry_after_s: u64 },
    #[error(transparent)]
    Db(#[from] sqlx::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

#[derive(Serialize)]
struct ErrEnvelope<'a> {
    error: ErrBody<'a>,
}
#[derive(Serialize)]
struct ErrBody<'a> {
    code: &'a str,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    details: Option<serde_json::Value>,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, message, details) = match &self {
            AppError::Validation { field, message } => (
                StatusCode::BAD_REQUEST,
                "VALIDATION_FAILED",
                message.clone(),
                Some(serde_json::json!({ "field": field })),
            ),
            AppError::Unauthorized => (
                StatusCode::UNAUTHORIZED,
                "UNAUTHORIZED",
                self.to_string(),
                None,
            ),
            AppError::Forbidden => (StatusCode::FORBIDDEN, "FORBIDDEN", self.to_string(), None),
            AppError::NotFound { kind } => (
                StatusCode::NOT_FOUND,
                "NOT_FOUND",
                format!("{kind} not found"),
                None,
            ),
            AppError::Conflict { kind } => (
                StatusCode::CONFLICT,
                "CONFLICT",
                format!("{kind} already exists"),
                None,
            ),
            AppError::RateLimited { retry_after_s } => {
                let mut resp = (
                    StatusCode::TOO_MANY_REQUESTS,
                    Json(ErrEnvelope {
                        error: ErrBody {
                            code: "RATE_LIMITED",
                            message: self.to_string(),
                            details: None,
                        },
                    }),
                )
                    .into_response();
                resp.headers_mut()
                    .insert("Retry-After", retry_after_s.to_string().parse().unwrap());
                return resp;
            }
            AppError::Db(e) => {
                tracing::error!(error = ?e, "db error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "INTERNAL_ERROR",
                    "internal error".into(),
                    None,
                )
            }
            AppError::Other(e) => {
                tracing::error!(error = ?e, "internal error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "INTERNAL_ERROR",
                    "internal error".into(),
                    None,
                )
            }
        };
        (
            status,
            Json(ErrEnvelope {
                error: ErrBody {
                    code,
                    message,
                    details,
                },
            }),
        )
            .into_response()
    }
}

pub type AppResult<T> = std::result::Result<T, AppError>;
