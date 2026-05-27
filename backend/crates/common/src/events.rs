use chrono::{DateTime, Utc};
use serde::Serialize;
use uuid::Uuid;

use crate::ids::new_id;

#[derive(Serialize)]
pub struct Envelope<T: Serialize> {
    pub event_id: Uuid,
    pub event_type: &'static str,
    pub event_version: u8,
    pub occurred_at: DateTime<Utc>,
    pub producer: &'static str,
    pub data: T,
}

impl<T: Serialize> Envelope<T> {
    pub fn new(event_type: &'static str, producer: &'static str, data: T) -> Self {
        Self {
            event_id: new_id(),
            event_type,
            event_version: 1,
            occurred_at: Utc::now(),
            producer,
            data,
        }
    }
}

#[derive(Serialize)]
pub struct ContentCreated {
    pub post_id: Uuid,
    pub author_id: Uuid,
    pub content: String,
    pub tags: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Serialize)]
pub struct UserFollowed {
    pub follower_id: Uuid,
    pub followee_id: Uuid,
    pub followed_at: DateTime<Utc>,
}

#[derive(Serialize)]
pub struct ModerationAction {
    pub actor_id: Uuid,
    pub target_user_id: Uuid,
    pub target_post_id: Option<Uuid>,
    pub report_id: Option<Uuid>,
    pub note: Option<String>,
}

pub const TOPIC_CONTENT_CREATED: &str = "oecophylla.content.created";
pub const TOPIC_USER_FOLLOWED: &str = "oecophylla.user.followed";
pub const TOPIC_INTERACTIONS: &str = "oecophylla.interactions";
pub const TOPIC_MODERATION_ACTION: &str = "oecophylla.moderation.action";
