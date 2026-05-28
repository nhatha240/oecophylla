use common::error::AppError;
use sqlx::PgPool;
use uuid::Uuid;

#[derive(sqlx::FromRow, serde::Serialize, Clone)]
pub struct ProfileRow {
    pub id: Uuid,
    pub username: String,
    pub display_name: Option<String>,
    pub bio: Option<String>,
    pub avatar_url: Option<String>,
    pub role: String,
    pub topic_prefs: Vec<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub async fn get_profile(db: &PgPool, id: Uuid) -> Result<Option<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT id, username, display_name, bio, avatar_url, role::text AS role, topic_prefs, created_at
         FROM users WHERE id = $1 AND is_active = true",
    )
    .bind(id)
    .fetch_optional(db)
    .await?)
}

pub async fn update_profile(
    db: &PgPool,
    id: Uuid,
    display_name: Option<&str>,
    bio: Option<&str>,
    avatar_url: Option<&str>,
    topic_prefs: Option<&[String]>,
) -> Result<ProfileRow, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "UPDATE users SET
            display_name = COALESCE($2, display_name),
            bio          = COALESCE($3, bio),
            avatar_url   = COALESCE($4, avatar_url),
            topic_prefs  = COALESCE($5, topic_prefs)
         WHERE id = $1
         RETURNING id, username, display_name, bio, avatar_url, role::text AS role, topic_prefs, created_at",
    )
    .bind(id)
    .bind(display_name)
    .bind(bio)
    .bind(avatar_url)
    .bind(topic_prefs)
    .fetch_one(db)
    .await?)
}

pub async fn insert_follow(db: &PgPool, follower: Uuid, followee: Uuid) -> Result<bool, AppError> {
    let r = sqlx::query(
        "INSERT INTO follows (follower_id, followee_id) VALUES ($1, $2)
         ON CONFLICT DO NOTHING",
    )
    .bind(follower)
    .bind(followee)
    .execute(db)
    .await?;
    Ok(r.rows_affected() == 1)
}

pub async fn delete_follow(db: &PgPool, follower: Uuid, followee: Uuid) -> Result<bool, AppError> {
    let r = sqlx::query("DELETE FROM follows WHERE follower_id=$1 AND followee_id=$2")
        .bind(follower)
        .bind(followee)
        .execute(db)
        .await?;
    Ok(r.rows_affected() == 1)
}

pub async fn list_followers(
    db: &PgPool,
    id: Uuid,
    limit: i64,
) -> Result<Vec<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT u.id, u.username, u.display_name, u.bio, u.avatar_url, u.role::text AS role, u.topic_prefs, u.created_at
         FROM follows f JOIN users u ON u.id = f.follower_id
         WHERE f.followee_id = $1 ORDER BY f.created_at DESC LIMIT $2",
    )
    .bind(id)
    .bind(limit)
    .fetch_all(db)
    .await?)
}

pub async fn list_following(
    db: &PgPool,
    id: Uuid,
    limit: i64,
) -> Result<Vec<ProfileRow>, AppError> {
    Ok(sqlx::query_as::<_, ProfileRow>(
        "SELECT u.id, u.username, u.display_name, u.bio, u.avatar_url, u.role::text AS role, u.topic_prefs, u.created_at
         FROM follows f JOIN users u ON u.id = f.followee_id
         WHERE f.follower_id = $1 ORDER BY f.created_at DESC LIMIT $2",
    )
    .bind(id)
    .bind(limit)
    .fetch_all(db)
    .await?)
}

pub async fn search_users(
    db: &PgPool,
    q: &str,
    limit: i64,
    page: i64,
) -> Result<(Vec<ProfileRow>, i64), AppError> {
    let offset = page * limit;

    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM users
         WHERE is_active = true
           AND (username ILIKE '%' || $1 || '%' OR display_name ILIKE '%' || $1 || '%')",
    )
    .bind(q)
    .fetch_one(db)
    .await?;

    let items = sqlx::query_as::<_, ProfileRow>(
        "SELECT id, username, display_name, bio, avatar_url, role::text AS role, topic_prefs, created_at
         FROM users
         WHERE is_active = true
           AND (username ILIKE '%' || $1 || '%' OR display_name ILIKE '%' || $1 || '%')
         ORDER BY
           CASE WHEN username ILIKE $1 || '%' THEN 0 ELSE 1 END,
           created_at DESC
         LIMIT $2 OFFSET $3",
    )
    .bind(q)
    .bind(limit)
    .bind(offset)
    .fetch_all(db)
    .await?;

    Ok((items, total))
}

#[derive(serde::Serialize, Clone)]
pub struct ProfileResponse {
    #[serde(flatten)]
    pub profile: ProfileRow,
    pub is_following: bool,
}

pub async fn get_profile_with_following(
    db: &PgPool,
    id: Uuid,
    viewer_id: Uuid,
) -> Result<Option<ProfileResponse>, AppError> {
    let profile = get_profile(db, id).await?;
    match profile {
        Some(profile) => {
            let is_following: bool = sqlx::query_scalar(
                "SELECT EXISTS(SELECT 1 FROM follows WHERE follower_id = $1 AND followee_id = $2)",
            )
            .bind(viewer_id)
            .bind(id)
            .fetch_one(db)
            .await?;
            Ok(Some(ProfileResponse {
                profile,
                is_following,
            }))
        }
        None => Ok(None),
    }
}

#[derive(sqlx::FromRow, serde::Serialize, Clone)]
pub struct SuggestionRow {
    pub id: Uuid,
    pub username: String,
    pub display_name: Option<String>,
    pub avatar_url: Option<String>,
    pub bio: Option<String>,
    pub mutual_count: i64,
}

pub async fn get_suggestions(
    db: &PgPool,
    user_id: Uuid,
    limit: i64,
) -> Result<Vec<SuggestionRow>, AppError> {
    Ok(sqlx::query_as::<_, SuggestionRow>(
        "SELECT u.id, u.username, u.display_name, u.avatar_url, u.bio,
                COUNT(DISTINCT f2.follower_id) AS mutual_count
         FROM follows f1
         JOIN follows f2 ON f2.follower_id = f1.followee_id
         JOIN users u ON u.id = f2.followee_id
         WHERE f1.follower_id = $1
           AND f2.followee_id != $1
           AND u.is_active = true
           AND f2.followee_id NOT IN (
             SELECT followee_id FROM follows WHERE follower_id = $1
           )
         GROUP BY u.id, u.username, u.display_name, u.avatar_url, u.bio, u.created_at
         ORDER BY mutual_count DESC, u.created_at DESC
         LIMIT $2",
    )
    .bind(user_id)
    .bind(limit)
    .fetch_all(db)
    .await?)
}

pub async fn fallback_suggestions(
    db: &PgPool,
    user_id: Uuid,
    limit: i64,
) -> Result<Vec<SuggestionRow>, AppError> {
    Ok(sqlx::query_as::<_, SuggestionRow>(
        "SELECT id, username, display_name, avatar_url, bio, 0::bigint AS mutual_count
         FROM users
         WHERE is_active = true AND id != $1
         ORDER BY created_at DESC
         LIMIT $2",
    )
    .bind(user_id)
    .bind(limit)
    .fetch_all(db)
    .await?)
}
