use serde::Serialize;
use uuid::Uuid;
#[allow(unused_imports)]
use common::events::Envelope;

pub const TOPIC_INTERACTIONS: &str = "oecophylla.interactions";

#[derive(Serialize)]
pub struct ToggleData { pub user_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub weight: f32 }
#[derive(Serialize)]
pub struct ReportData { pub reporter_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub reason: String, pub report_id: Uuid }
#[derive(Serialize)]
pub struct CommentData { pub commenter_id: Uuid, pub post_id: Uuid, pub post_author_id: Uuid, pub comment_id: Uuid, pub parent_comment_id: Option<Uuid>, pub content_preview: String }

pub fn weight_for(t: &str) -> f32 {
    match t {
        "like" => env_or("INTERACTION_WEIGHT_LIKE", 1.5),
        "save" => env_or("INTERACTION_WEIGHT_SAVE", 2.5),
        "share" => env_or("INTERACTION_WEIGHT_SHARE", 2.5),
        "hide" => env_or("INTERACTION_WEIGHT_HIDE", -2.0),
        "report" => env_or("INTERACTION_WEIGHT_REPORT", -5.0),
        _ => 0.0,
    }
}
fn env_or(key: &str, default: f32) -> f32 {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}

pub fn counter_column(t: &str) -> Option<&'static str> {
    match t { "like" => Some("like_count"), "save" => Some("save_count"), "share" => Some("share_count"), _ => None }
}
