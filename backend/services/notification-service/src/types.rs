use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Slim actor snapshot attached to a notification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActorDto {
    pub id: Uuid,
    pub username: String,
    pub avatar_url: Option<String>,
}

/// First 100 chars of the post content so the UI can show context.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PostSnippet {
    pub id: Uuid,
    pub snippet: String,
}

/// Wire representation of a notification returned by the REST API and SSE stream.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationDto {
    pub id: Uuid,
    /// Text representation of `notification_kind` (e.g. `"liked"`, `"followed"`).
    pub kind: String,
    pub actor: Option<ActorDto>,
    pub post: Option<PostSnippet>,
    pub comment_id: Option<Uuid>,
    pub payload: serde_json::Value,
    pub read: bool,
    pub created_at: DateTime<Utc>,
}

// ── Query params ─────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default)]
    pub cursor: Option<String>,
    #[serde(default = "default_limit")]
    pub limit: i64,
    #[serde(default)]
    pub unread_only: bool,
}

fn default_limit() -> i64 {
    20
}

// ── Response envelopes ────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct NotificationListResponse {
    pub items: Vec<NotificationDto>,
    pub next_cursor: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UnreadCountResponse {
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct MarkAllReadResponse {
    pub count: i64,
}
