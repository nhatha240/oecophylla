#![allow(dead_code)]

use common::{config::SharedConfig, models::UserRole};
use sqlx::PgPool;
use std::sync::Arc;
use uuid::Uuid;

pub async fn setup() -> (PgPool, deadpool_redis::Pool, Arc<SharedConfig>) {
    // Explicit opt-in: never fall back to the application's database or Redis.
    let database_url = std::env::var("REVIEW_DATABASE_URL")
        .expect("set REVIEW_DATABASE_URL to an isolated test database");
    let redis_url =
        std::env::var("REVIEW_REDIS_URL").expect("set REVIEW_REDIS_URL to isolated test Redis");
    let db = PgPool::connect(&database_url).await.unwrap();
    sqlx::migrate!("../../../migrations")
        .run(&db)
        .await
        .unwrap();
    let redis = common::redis::redis_pool(&redis_url).unwrap();
    let cfg = Arc::new(SharedConfig {
        database_url,
        redis_url,
        kafka_brokers: "127.0.0.1:19092".into(),
        jwt_secret: "isolated-review-test-secret".into(),
        jwt_access_ttl_seconds: 900,
        jwt_refresh_ttl_seconds: 3600,
        cookie_secure: false,
        argon2_m_cost: 8,
        argon2_t_cost: 1,
        argon2_p_cost: 1,
        auto_publish: true,
        bind: "127.0.0.1:0".into(),
    });
    (db, redis, cfg)
}

pub async fn user(db: &PgPool, role: UserRole) -> Uuid {
    let id = Uuid::now_v7();
    let suffix = id.simple().to_string();
    let hash = common::auth::hash_password("Password!123", 8, 1, 1).unwrap();
    sqlx::query(
        "INSERT INTO users (id, username, email, password_hash, role) VALUES ($1,$2,$3,$4,$5)",
    )
    .bind(id)
    .bind(format!("u{}", &suffix[22..]))
    .bind(format!("{suffix}@review.test"))
    .bind(hash)
    .bind(role)
    .execute(db)
    .await
    .unwrap();
    id
}

pub fn cookie(cfg: &SharedConfig, id: Uuid, role: UserRole) -> String {
    format!(
        "oec_access={}",
        common::auth::issue_access(cfg.jwt_secret.as_bytes(), 900, id, role).unwrap()
    )
}

pub async fn serve(app: axum::Router) -> (String, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    let task = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    (url, task)
}
