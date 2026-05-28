use chrono::{DateTime, Utc};
use serde::Serialize;
use uuid::Uuid;

/// Wire representation of a comment for SSE streaming.
#[derive(Debug, Clone, Serialize, sqlx::FromRow)]
pub struct CommentDto {
    pub id: Uuid,
    pub post_id: Uuid,
    pub author_id: Uuid,
    pub author_username: String,
    pub author_display_name: Option<String>,
    pub content: String,
    pub parent_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
}
