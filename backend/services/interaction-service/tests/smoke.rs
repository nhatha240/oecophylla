//! Pre: docker compose stack up incl. interaction-service. Tests use Envoy (:8080).

use reqwest::{Client, StatusCode};
use serde_json::json;
use std::process::Command;

const ENVOY: &str = "http://localhost:8080";

fn cli() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}

async fn register_user(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c.post(format!("{ENVOY}/api/v1/auth/register"))
        .json(&json!({ "username": format!("u{}", &u[22..]), "email": format!("{u}@e.com"), "password": "Password!123" }))
        .send().await.unwrap();
    assert_eq!(
        r.status(),
        200,
        "register failed: {}",
        r.text().await.unwrap()
    );
    r.json().await.unwrap()
}

async fn create_post(c: &Client, content: &str) -> serde_json::Value {
    let r = c
        .post(format!("{ENVOY}/api/v1/posts"))
        .json(&json!({ "content": content }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "create_post failed");
    r.json().await.unwrap()
}

async fn get_post(c: &Client, id: &str) -> serde_json::Value {
    let r = c
        .get(format!("{ENVOY}/api/v1/posts/{id}"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    r.json().await.unwrap()
}

#[tokio::test]
async fn like_is_idempotent_and_counts() {
    let a = cli();
    let _ = register_user(&a).await;
    let p = create_post(&a, "for like tests").await;
    let pid = p["id"].as_str().unwrap();

    // 1st like -> 201
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/like"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    // 2nd like -> 200 (idempotent)
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/like"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    // counter == 1
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 1);
    // unlike -> 204
    let r = a
        .delete(format!("{ENVOY}/api/v1/posts/{pid}/like"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::NO_CONTENT);
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 0);
}

#[tokio::test]
async fn hide_does_not_bump_like_count() {
    let a = cli();
    let _ = register_user(&a).await;
    let p = create_post(&a, "for hide test").await;
    let pid = p["id"].as_str().unwrap();
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/hide"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    let post = get_post(&a, pid).await;
    assert_eq!(post["like_count"], 0);
    assert_eq!(post["save_count"], 0);
}

#[tokio::test]
async fn report_duplicate_pending_409() {
    let a = cli();
    let b = cli();
    let _ = register_user(&a).await;
    let _ = register_user(&b).await;
    let p = create_post(&b, "for reports").await;
    let pid = p["id"].as_str().unwrap();
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::CONFLICT);
}

#[tokio::test]
async fn comment_reply_then_reject_nested() {
    let a = cli();
    let _ = register_user(&a).await;
    let p = create_post(&a, "for comments").await;
    let pid = p["id"].as_str().unwrap();
    // top-level
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "top-level" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let top_id = r.json::<serde_json::Value>().await.unwrap()["id"]
        .as_str()
        .unwrap()
        .to_string();
    // reply
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "reply", "parent_comment_id": top_id }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let reply_id = r.json::<serde_json::Value>().await.unwrap()["id"]
        .as_str()
        .unwrap()
        .to_string();
    // reject nested
    let r = a
        .post(format!("{ENVOY}/api/v1/posts/{pid}/comments"))
        .json(&json!({ "content": "nested", "parent_comment_id": reply_id }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);
    // comment_count = 1 (top only)
    let post = get_post(&a, pid).await;
    assert_eq!(post["comment_count"], 1);
}

#[tokio::test]
async fn my_endpoint_reflects_state() {
    let a = cli();
    let b = cli();
    let _ = register_user(&a).await;
    let _ = register_user(&b).await;
    let p = create_post(&b, "for /me test").await;
    let pid = p["id"].as_str().unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/like"))
        .send()
        .await
        .unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/save"))
        .send()
        .await
        .unwrap();
    let r = a
        .get(format!("{ENVOY}/api/v1/posts/{pid}/me"))
        .send()
        .await
        .unwrap();
    let me: serde_json::Value = r.json().await.unwrap();
    assert_eq!(me["liked"], true);
    assert_eq!(me["saved"], true);
    assert_eq!(me["shared"], false);
}

#[tokio::test]
async fn batch_me_endpoint_reflects_state_and_validates_length() {
    let a = cli();
    let b = cli();
    let _ = register_user(&a).await;
    let _ = register_user(&b).await;
    let p1 = create_post(&b, "for batch /me test").await;
    let p2 = create_post(&b, "for batch /me empty test").await;
    let pid1 = p1["id"].as_str().unwrap();
    let pid2 = p2["id"].as_str().unwrap();

    a.post(format!("{ENVOY}/api/v1/posts/{pid1}/like"))
        .send()
        .await
        .unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid1}/save"))
        .send()
        .await
        .unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid1}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();

    let r = a
        .post(format!("{ENVOY}/api/v1/interactions/me/batch"))
        .json(&json!({ "post_ids": [pid1, pid2] }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let body: serde_json::Value = r.json().await.unwrap();
    assert_eq!(body["items"][pid1]["liked"], true);
    assert_eq!(body["items"][pid1]["saved"], true);
    assert_eq!(body["items"][pid1]["shared"], false);
    assert_eq!(body["items"][pid1]["hidden"], false);
    assert_eq!(body["items"][pid1]["reported_pending"], true);
    assert_eq!(body["items"][pid2]["liked"], false);
    assert_eq!(body["items"][pid2]["saved"], false);
    assert_eq!(body["items"][pid2]["shared"], false);
    assert_eq!(body["items"][pid2]["hidden"], false);
    assert_eq!(body["items"][pid2]["reported_pending"], false);

    let too_many = (0..101)
        .map(|_| uuid::Uuid::now_v7().to_string())
        .collect::<Vec<_>>();
    let r = a
        .post(format!("{ENVOY}/api/v1/interactions/me/batch"))
        .json(&json!({ "post_ids": too_many }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn kafka_emits_liked_event() {
    let a = cli();
    let _ = register_user(&a).await;
    let p = create_post(&a, "for kafka").await;
    let pid = p["id"].as_str().unwrap();
    a.post(format!("{ENVOY}/api/v1/posts/{pid}/like"))
        .send()
        .await
        .unwrap();
    // poll kafka topic via docker exec — read up to 50 messages so we find the liked event
    // even if earlier tests have already written other event types to the topic.
    let out = Command::new("docker")
        .args([
            "compose",
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-consumer.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "oecophylla.interactions",
            "--from-beginning",
            "--max-messages",
            "50",
            "--timeout-ms",
            "5000",
        ])
        .output()
        .expect("docker exec failed");
    let body = String::from_utf8_lossy(&out.stdout);
    assert!(body.contains("\"event_type\":\"liked\""), "stdout: {body}");
}

/// Per-route rate limit. Run only when the `report` bucket is throttled to a
/// tiny ceiling for the duration of this test:
///
/// ```
/// docker compose stop interaction-service
/// RATE_LIMIT_REPORT=2 docker compose up -d interaction-service
/// cargo test -p interaction-service --test smoke -- --ignored \
///   report_route_returns_429_under_low_limit
/// docker compose up -d interaction-service   # restore default limit
/// ```
#[tokio::test]
#[ignore = "requires RATE_LIMIT_REPORT=2 env on interaction-service"]
async fn report_route_returns_429_under_low_limit() {
    let reporter = cli();
    let _ = register_user(&reporter).await;

    let author = cli();
    let _ = register_user(&author).await;
    let post = create_post(&author, "for rate limit smoke").await;
    let pid = post["id"].as_str().unwrap();

    let mut statuses = Vec::new();
    for _ in 0..5 {
        let r = reporter
            .post(format!("{ENVOY}/api/v1/posts/{pid}/report"))
            .json(&json!({ "reason": "spam" }))
            .send()
            .await
            .unwrap();
        statuses.push(r.status());
    }
    assert!(
        statuses.iter().any(|s| *s == StatusCode::TOO_MANY_REQUESTS),
        "expected 429 in statuses {statuses:?}"
    );
}
