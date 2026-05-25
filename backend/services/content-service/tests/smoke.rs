//! Smoke tests.
//!
//! Pre-conditions:
//!   - Postgres, Redis, Kafka running via compose
//!   - auth-service on 8001 and content-service on 8003
//!   - Services should be able to resolve Kafka as `kafka:9092`.

use reqwest::{Client, StatusCode};
use serde_json::json;
use std::time::Duration;

fn cli() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}

const AUTH: &str = "http://127.0.0.1:8001";
const CONTENT: &str = "http://127.0.0.1:8003";

async fn register(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    let r = c
        .post(format!("{AUTH}/api/v1/auth/register"))
        .json(&json!({
            "username": format!("u{}", &u[22..]),
            "email": format!("{u}@e.com"),
            "password": "Password!123"
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    r.json::<serde_json::Value>().await.unwrap()
}

fn kafka_current_offset() -> u64 {
    let out = std::process::Command::new("docker")
        .args([
            "exec",
            "oecophylla-kafka-1",
            "/opt/kafka/bin/kafka-get-offsets.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "oecophylla.content.created",
        ])
        .output()
        .expect("docker exec kafka-get-offsets failed");
    let s = String::from_utf8_lossy(&out.stdout);
    s.trim()
        .split(':')
        .last()
        .and_then(|x| x.parse::<u64>().ok())
        .unwrap_or(0)
}

fn kafka_consume_one(offset: u64) -> serde_json::Value {
    for attempt in 0..5 {
        let out = std::process::Command::new("docker")
            .args([
                "exec",
                "oecophylla-kafka-1",
                "/opt/kafka/bin/kafka-console-consumer.sh",
                "--bootstrap-server",
                "kafka:9092",
                "--topic",
                "oecophylla.content.created",
                "--offset",
                &offset.to_string(),
                "--partition",
                "0",
                "--max-messages",
                "1",
                "--timeout-ms",
                "2000",
            ])
            .output()
            .expect("docker exec kafka-console-consumer failed");
        let stdout = String::from_utf8_lossy(&out.stdout);
        if let Some(line) = stdout.lines().find(|l| l.starts_with('{')) {
            return serde_json::from_str(line).expect("failed to parse kafka message as JSON");
        }
        if attempt < 4 {
            std::thread::sleep(Duration::from_secs(1));
        }
    }
    panic!("kafka message did not arrive at offset {offset} within 10 seconds");
}

#[tokio::test]
async fn post_create_publishes_event_and_validates() {
    let c = cli();
    let _ = register(&c).await;

    let r = c
        .post(format!("{CONTENT}/api/v1/posts"))
        .json(&json!({ "content": "" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);

    let start_offset = kafka_current_offset();

    let r = c
        .post(format!("{CONTENT}/api/v1/posts"))
        .json(&json!({ "content": "Hello world", "tags": ["greet"] }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let post: serde_json::Value = r.json().await.unwrap();
    assert_eq!(post["status"], "published");

    let env = kafka_consume_one(start_offset);
    assert_eq!(env["data"]["post_id"], post["id"]);
}

#[tokio::test]
async fn list_by_author_paginates() {
    let c = cli();
    let u = register(&c).await;
    let id = u["user"]["id"].as_str().unwrap();
    for i in 0..3 {
        c.post(format!("{CONTENT}/api/v1/posts"))
            .json(&json!({ "content": format!("p{i}") }))
            .send()
            .await
            .unwrap();
    }
    let r = c
        .get(format!("{CONTENT}/api/v1/posts?author_id={id}&limit=10"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let arr: serde_json::Value = r.json().await.unwrap();
    assert!(arr.as_array().unwrap().len() >= 3);
}

#[tokio::test]
async fn delete_non_owner_forbidden() {
    let a = cli();
    let b = cli();
    let _ = register(&a).await;
    let _ = register(&b).await;
    let r = a
        .post(format!("{CONTENT}/api/v1/posts"))
        .json(&json!({ "content": "mine" }))
        .send()
        .await
        .unwrap();
    let post: serde_json::Value = r.json().await.unwrap();
    let pid = post["id"].as_str().unwrap();
    let r = b
        .delete(format!("{CONTENT}/api/v1/posts/{pid}"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::FORBIDDEN);
}
