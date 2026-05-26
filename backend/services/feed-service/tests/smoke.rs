//! Pre: docker compose stack up incl. feed-service. Tests use Envoy (:8080).

use reqwest::{Client, StatusCode};
use serde_json::json;

const ENVOY: &str = "http://localhost:8080";

fn cli() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}

async fn register_user(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c
        .post(format!("{ENVOY}/api/v1/auth/register"))
        .json(&json!({
            "username": format!("u{}", &u[22..]),
            "email": format!("{u}@e.com"),
            "password": "Password!123",
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "register: {}", r.text().await.unwrap());
    r.json().await.unwrap()
}

async fn create_post(c: &Client, content: &str) {
    let r = c
        .post(format!("{ENVOY}/api/v1/posts"))
        .json(&json!({ "content": content }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "create_post: {}", r.text().await.unwrap());
}

#[tokio::test]
async fn unauthenticated_feed_returns_401() {
    let c = cli();
    let r = c
        .get(format!("{ENVOY}/api/v1/feed"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn authenticated_feed_serves_items() {
    let author = cli();
    let _ = register_user(&author).await;
    create_post(&author, "post for feed smoke").await;

    let viewer = cli();
    let _ = register_user(&viewer).await;
    let r = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=5"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "feed: {}", r.text().await.unwrap());
    let body: serde_json::Value = r.json().await.unwrap();
    let items = body["items"].as_array().expect("items array");
    assert!(
        !items.is_empty(),
        "expected at least one feed item, got {body}"
    );
    let source = body["source"].as_str().unwrap();
    assert!(
        ["cache", "personalized", "fallback"].contains(&source),
        "unexpected source {source}"
    );
}

/// Second request hits the Redis cache populated by the first request.
#[tokio::test]
async fn second_feed_request_hits_cache() {
    let author = cli();
    let _ = register_user(&author).await;
    create_post(&author, "post for cache hit").await;

    let viewer = cli();
    let _ = register_user(&viewer).await;
    let _ = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=5"))
        .send()
        .await
        .unwrap();
    let r = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=5"))
        .send()
        .await
        .unwrap();
    let body: serde_json::Value = r.json().await.unwrap();
    assert_eq!(body["source"], "cache");
}

#[tokio::test]
async fn cursor_pages_do_not_overlap() {
    // Author posts 6 items so we have at least 2 pages with limit=3.
    let author = cli();
    let _ = register_user(&author).await;
    for i in 0..6 {
        create_post(&author, &format!("paginated post {i}")).await;
    }
    let viewer = cli();
    let _ = register_user(&viewer).await;

    let page1: serde_json::Value = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=3"))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let cursor = page1["next_cursor"]
        .as_str()
        .expect("next_cursor present after page 1");
    let page1_ids: Vec<String> = page1["items"]
        .as_array()
        .unwrap()
        .iter()
        .map(|i| i["id"].as_str().unwrap().to_string())
        .collect();

    let page2: serde_json::Value = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=3&cursor={cursor}"))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let page2_ids: Vec<String> = page2["items"]
        .as_array()
        .unwrap()
        .iter()
        .map(|i| i["id"].as_str().unwrap().to_string())
        .collect();

    assert!(
        page1_ids.iter().all(|id| !page2_ids.contains(id)),
        "pages overlap: {page1_ids:?} vs {page2_ids:?}"
    );
}

/// Run with `RECOMMENDATION_SERVICE_URL=http://10.255.255.1:8090 docker compose up -d feed-service`
/// and `cargo test -p feed-service --test smoke -- --ignored fallback_when_recommendation_unreachable`.
#[tokio::test]
#[ignore = "requires unreachable RECOMMENDATION_SERVICE_URL on feed-service"]
async fn fallback_when_recommendation_unreachable() {
    let author = cli();
    let _ = register_user(&author).await;
    create_post(&author, "post for fallback").await;

    let viewer = cli();
    let _ = register_user(&viewer).await;
    let r = viewer
        .get(format!("{ENVOY}/api/v1/feed?limit=5"))
        .send()
        .await
        .unwrap();
    let body: serde_json::Value = r.json().await.unwrap();
    assert_eq!(body["source"], "fallback");
}
