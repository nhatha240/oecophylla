use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct FeedPostRow {
    pub id: Uuid,
    pub author_id: Uuid,
    pub username: String,
    pub display_name: Option<String>,
    pub avatar_url: Option<String>,
    pub content: String,
    pub media_urls: Vec<String>,
    pub tags: Vec<String>,
    pub topics: Vec<String>,
    pub safety_score: f32,
    pub like_count: i32,
    pub comment_count: i32,
    pub save_count: i32,
    pub share_count: i32,
    pub view_count: i64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct FeedRank {
    pub score: f32,
    pub source: String,
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct FeedItem {
    #[serde(flatten)]
    pub post: FeedPostRow,
    pub rank: FeedRank,
}

#[derive(Debug, Serialize)]
pub struct FeedResponse {
    pub items: Vec<FeedItem>,
    pub next_cursor: Option<String>,
    pub source: String,
    pub generated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct FeedQuery {
    pub cursor: Option<String>,
    #[serde(default)]
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CachedFeedItem {
    pub post_id: Uuid,
    pub score: f32,
    pub source: String,
    pub reason: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CachedFeed {
    pub generated_at: DateTime<Utc>,
    pub source: String,
    pub items: Vec<CachedFeedItem>,
}
