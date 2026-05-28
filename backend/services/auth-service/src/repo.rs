use common::{error::AppError, models::UserRole};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, Clone)]
pub struct UserRow {
    pub id: Uuid,
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub role: UserRole,
    pub display_name: Option<String>,
    pub avatar_url: Option<String>,
    pub topic_prefs: Vec<String>,
}

pub async fn insert_user(
    db: &PgPool,
    username: &str,
    email: &str,
    password_hash: &str,
    display_name: Option<&str>,
) -> Result<UserRow, AppError> {
    sqlx::query_as::<_, UserRow>(
        "INSERT INTO users (username, email, password_hash, display_name)
         VALUES ($1, $2, $3, $4)
         RETURNING id, username, email, password_hash, role, display_name, avatar_url, topic_prefs",
    )
    .bind(username)
    .bind(email)
    .bind(password_hash)
    .bind(display_name)
    .fetch_one(db)
    .await
    .map_err(|e| match e {
        sqlx::Error::Database(d) if d.code().as_deref() == Some("23505") => AppError::Conflict {
            kind: "user".into(),
        },
        other => AppError::Db(other),
    })
}

pub async fn find_by_email_or_username(
    db: &PgPool,
    key: &str,
) -> Result<Option<UserRow>, AppError> {
    Ok(sqlx::query_as::<_, UserRow>(
        "SELECT id, username, email, password_hash, role, display_name, avatar_url, topic_prefs
         FROM users WHERE email = $1 OR username = $1",
    )
    .bind(key)
    .fetch_optional(db)
    .await?)
}

pub async fn find_by_id(db: &PgPool, id: Uuid) -> Result<Option<UserRow>, AppError> {
    Ok(sqlx::query_as::<_, UserRow>(
        "SELECT id, username, email, password_hash, role, display_name, avatar_url, topic_prefs
         FROM users WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(db)
    .await?)
}

pub async fn update_password(db: &PgPool, user_id: Uuid, new_hash: &str) -> Result<(), AppError> {
    sqlx::query("UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2")
        .bind(new_hash)
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(())
}

pub async fn deactivate_user(db: &PgPool, user_id: Uuid) -> Result<(), AppError> {
    sqlx::query("UPDATE users SET is_active = false, updated_at = NOW() WHERE id = $1")
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(())
}
