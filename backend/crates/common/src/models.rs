use serde::{Deserialize, Serialize};
use sqlx::Type;
use uuid::Uuid;

#[derive(Debug, Copy, Clone, PartialEq, Eq, Type, Serialize, Deserialize)]
#[sqlx(type_name = "user_role", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum UserRole {
    User,
    Creator,
    Admin,
}

#[derive(Debug, Copy, Clone, PartialEq, Eq, Type, Serialize, Deserialize)]
#[sqlx(type_name = "post_status", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum PostStatus {
    Pending,
    Published,
    Hidden,
    Flagged,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct AuthUser {
    pub id: Uuid,
    pub role: UserRole,
}
