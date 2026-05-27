use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Query params for `GET /admin/reports`.
#[derive(Debug, Deserialize)]
pub struct ReportListQuery {
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub cursor: Option<String>,
    #[serde(default)]
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct ReportListItem {
    pub id: Uuid,
    pub reporter_id: Option<Uuid>,
    pub reporter_username: Option<String>,
    pub post_id: Uuid,
    pub post_snippet: Option<String>,
    pub reason: String,
    pub detail: Option<String>,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct ReportListResponse {
    pub items: Vec<ReportListItem>,
    pub next_cursor: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ReportDetail {
    pub id: Uuid,
    pub reporter_id: Option<Uuid>,
    pub reporter_username: Option<String>,
    pub post_id: Uuid,
    pub post_author_id: Option<Uuid>,
    pub post_snippet: Option<String>,
    pub reason: String,
    pub detail: Option<String>,
    pub status: String,
    pub resolved_by: Option<Uuid>,
    pub resolved_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct AuditListQuery {
    #[serde(default)]
    pub actor_id: Option<Uuid>,
    #[serde(default)]
    pub action: Option<String>,
    #[serde(default)]
    pub cursor: Option<String>,
    #[serde(default)]
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct AuditListItem {
    pub id: Uuid,
    pub actor_id: Uuid,
    pub action: String,
    pub target_type: String,
    pub target_id: Uuid,
    pub report_id: Option<Uuid>,
    pub note: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct AuditListResponse {
    pub items: Vec<AuditListItem>,
    pub next_cursor: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UserHistoryResponse {
    pub user_id: Uuid,
    pub reports: Vec<ReportListItem>,
    pub audit_entries: Vec<AuditListItem>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResolveAction {
    Dismiss,
    HidePost,
    WarnAuthor,
    BanAuthor,
}

#[derive(Debug, Deserialize)]
pub struct ResolveRequest {
    pub action: ResolveAction,
    #[serde(default)]
    pub note: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ResolveResponse {
    pub report_id: Uuid,
    pub status: String,
    pub action: String,
}
