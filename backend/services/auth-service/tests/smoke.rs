//! Smoke tests assume auth-service is running on http://127.0.0.1:8001 against
//! the same Postgres/Redis from compose.dev.yaml. Run with:
//!   docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka
//!   cargo run -p auth-service &
//!   cargo test -p auth-service --test smoke -- --test-threads=1

use reqwest::{Client, StatusCode};
use serde_json::json;

fn client() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}
const BASE: &str = "http://127.0.0.1:8001";

#[tokio::test]
async fn register_login_refresh_logout() {
    let c = client();
    let uniq = uuid::Uuid::now_v7().simple().to_string();
    let username = format!("u{}", &uniq[..10]);
    let email = format!("{username}@example.com");

    // Register
    let r = c.post(format!("{BASE}/api/v1/auth/register"))
        .json(&json!({ "username": username, "email": email, "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let user: serde_json::Value = r.json().await.unwrap();
    assert!(user["user"]["id"].as_str().unwrap().len() == 36);

    // Duplicate
    let r = c.post(format!("{BASE}/api/v1/auth/register"))
        .json(&json!({ "username": username, "email": email, "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::CONFLICT);

    // Wrong password → 401, no leak
    let r = c.post(format!("{BASE}/api/v1/auth/login"))
        .json(&json!({ "email_or_username": email, "password": "wrong" }))
        .send().await.unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);

    // Refresh rotates
    let r = c.post(format!("{BASE}/api/v1/auth/refresh")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);

    // Logout invalidates refresh
    let r = c.delete(format!("{BASE}/api/v1/auth/logout")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::NO_CONTENT);
    let r = c.post(format!("{BASE}/api/v1/auth/refresh")).send().await.unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);
}
