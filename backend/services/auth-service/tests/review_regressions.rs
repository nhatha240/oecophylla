#![allow(dead_code)]
#[path = "../src/handlers.rs"]
mod handlers;
#[path = "../src/repo.rs"]
mod repo;
#[path = "../src/state.rs"]
mod state;
#[path = "../../../tests/support/review.rs"]
mod support;

use axum::{
    routing::{get, post},
    Router,
};
use common::models::UserRole;
use reqwest::{Client, StatusCode};
use serde_json::json;

#[tokio::test]
async fn inactive_accounts_cannot_login_refresh_or_load_me() {
    let (db, redis, cfg) = support::setup().await;
    let id = support::user(&db, UserRole::User).await;
    let suffix = id.simple().to_string();
    let username = format!("u{}", &suffix[22..]);
    let email = format!("{suffix}@review.test");
    let app = Router::new()
        .route("/api/v1/auth/login", post(handlers::login))
        .route("/api/v1/auth/refresh", post(handlers::refresh))
        .route("/api/v1/auth/me", get(handlers::me))
        .with_state(state::AppState {
            db: db.clone(),
            redis,
            cfg,
        });
    let (base, task) = support::serve(app).await;
    let client = Client::builder().cookie_store(true).build().unwrap();
    let login = client
        .post(format!("{base}/api/v1/auth/login"))
        .json(&json!({"email_or_username": email, "password": "Password!123"}))
        .send()
        .await
        .unwrap();
    assert_eq!(login.status(), StatusCode::OK);
    repo::deactivate_user(&db, id).await.unwrap();
    let mut statuses = Vec::new();
    for identity in [email, username] {
        statuses.push(
            Client::new()
                .post(format!("{base}/api/v1/auth/login"))
                .json(&json!({"email_or_username": identity, "password": "Password!123"}))
                .send()
                .await
                .unwrap()
                .status(),
        );
    }
    statuses.push(
        client
            .post(format!("{base}/api/v1/auth/refresh"))
            .send()
            .await
            .unwrap()
            .status(),
    );
    statuses.push(
        client
            .get(format!("{base}/api/v1/auth/me"))
            .send()
            .await
            .unwrap()
            .status(),
    );
    task.abort();
    assert_eq!(
        statuses,
        vec![StatusCode::UNAUTHORIZED; 4],
        "email login, username login, refresh, me must all reject inactive accounts"
    );
}
