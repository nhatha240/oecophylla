#![allow(dead_code)]
#[path = "../src/avatar.rs"]
mod avatar;
#[path = "../src/handlers.rs"]
mod handlers;
#[path = "../src/repo.rs"]
mod repo;
#[path = "../src/state.rs"]
mod state;
#[path = "../../../tests/support/review.rs"]
mod support;

use axum::{extract::DefaultBodyLimit, routing::get, Router};
use common::models::UserRole;
use reqwest::{Client, StatusCode};
use serde_json::{json, Value};

#[tokio::test]
async fn uploaded_avatar_survives_profile_save_but_arbitrary_local_urls_are_rejected() {
    let (db, redis, cfg) = support::setup().await;
    let owner = support::user(&db, UserRole::User).await;
    let cookie = support::cookie(&cfg, owner, UserRole::User);
    let app = Router::new()
        .route(
            "/api/v1/users/{id}",
            get(handlers::get).put(handlers::update),
        )
        .route(
            "/api/v1/users/{id}/avatar",
            get(handlers::avatar).put(handlers::upload_avatar),
        )
        .layer(DefaultBodyLimit::max(avatar::MAX_AVATAR_BYTES + 65536))
        .with_state(state::AppState {
            db,
            redis,
            cfg,
            kafka: common::kafka::Producer::new("").unwrap(),
        });
    let (base, task) = support::serve(app).await;
    let client = Client::new();
    let bytes = b"\x89PNG\r\n\x1a\nreview-image";
    let mut payload = b"--review\r\nContent-Disposition: form-data; name=\"avatar\"; filename=\"avatar.png\"\r\nContent-Type: image/png\r\n\r\n".to_vec();
    payload.extend_from_slice(bytes);
    payload.extend_from_slice(b"\r\n--review--\r\n");
    let uploaded = client
        .put(format!("{base}/api/v1/users/{owner}/avatar"))
        .header("cookie", &cookie)
        .header("content-type", "multipart/form-data; boundary=review")
        .body(payload)
        .send()
        .await
        .unwrap();
    assert_eq!(uploaded.status(), StatusCode::OK);
    let url = uploaded.json::<Value>().await.unwrap()["avatar_url"]
        .as_str()
        .unwrap()
        .to_owned();
    assert_eq!(
        client
            .get(format!("{base}{url}"))
            .send()
            .await
            .unwrap()
            .bytes()
            .await
            .unwrap()
            .as_ref(),
        bytes
    );
    let mut statuses = Vec::new();
    for candidate in [
        &url,
        "/api/v1/users/someone-else/avatar?v=fake",
        "//example.test/avatar",
        "javascript:alert(1)",
        "https://cdn.example.test/avatar.png",
    ] {
        statuses.push(client.put(format!("{base}/api/v1/users/{owner}"))
            .header("cookie", &cookie).json(&json!({"display_name": "Edited name", "bio": "Edited bio", "avatar_url": candidate}))
            .send().await.unwrap().status());
    }
    task.abort();
    assert_eq!(
        statuses,
        vec![
            StatusCode::OK,
            StatusCode::BAD_REQUEST,
            StatusCode::BAD_REQUEST,
            StatusCode::BAD_REQUEST,
            StatusCode::OK
        ]
    );
}
