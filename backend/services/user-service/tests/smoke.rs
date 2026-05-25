//! Smoke tests.
//!
//! Pre-conditions:
//!   - Postgres, Redis, Kafka running via compose  
//!   - auth-service on 8001 and user-service on 8002
//!   - When running natively, Kafka must be resolvable (add `127.0.0.1 kafka` to
//!     /etc/hosts or run services in docker-compose with kafka:9092 accessible)
//!   - The preferred approach: run auth-service and user-service in docker compose
//!     (or docker run --network oecophylla_default) so they can reach kafka:9092.
//!     The test binary still runs on the host and contacts services via exposed ports.
//!
//! Run:
//!   docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
//!   # Either native (needs 127.0.0.1 kafka in /etc/hosts):
//!   cargo run -p auth-service & cargo run -p user-service &
//!   # Or docker (recommended):
//!   docker run -d --network oecophylla_default -p 8001:8001 ... oecophylla-auth-service
//!   docker run -d --network oecophylla_default -p 8002:8002 ... oecophylla-user-service
//!   cargo test -p user-service --test smoke -- --test-threads=1

use reqwest::{Client, StatusCode};
use serde_json::json;
use std::time::Duration;

fn cli() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}
const AUTH: &str = "http://127.0.0.1:8001";
const USER: &str = "http://127.0.0.1:8002";

async fn register(c: &Client) -> serde_json::Value {
    let u = uuid::Uuid::now_v7().simple().to_string();
    // Use the random tail (chars 22-31) for username to avoid timestamp collisions
    // when two UUIDs are generated within the same 256 ms window.
    let r = c
        .post(format!("{AUTH}/api/v1/auth/register"))
        .json(&json!({
            "username": format!("u{}", &u[22..]),
            "email":    format!("{u}@e.com"),
            "password": "Password!123"
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    r.json::<serde_json::Value>().await.unwrap()
}

/// Get the current latest offset for the user.followed topic (partition 0).
fn kafka_current_offset() -> u64 {
    let out = std::process::Command::new("docker")
        .args([
            "exec",
            "oecophylla-kafka-1",
            "/opt/kafka/bin/kafka-get-offsets.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "oecophylla.user.followed",
        ])
        .output()
        .expect("docker exec kafka-get-offsets failed");
    let s = String::from_utf8_lossy(&out.stdout);
    // Format: "oecophylla.user.followed:0:<offset>\n"
    s.trim()
        .split(':')
        .last()
        .and_then(|x| x.parse::<u64>().ok())
        .unwrap_or(0)
}

/// Consume one message from the user.followed topic starting at `offset` via docker exec.
/// Returns the parsed JSON envelope or panics on timeout/parse failure.
fn kafka_consume_one(offset: u64) -> serde_json::Value {
    // retry a few times to allow the producer to deliver the message
    for attempt in 0..5 {
        let out = std::process::Command::new("docker")
            .args([
                "exec",
                "oecophylla-kafka-1",
                "/opt/kafka/bin/kafka-console-consumer.sh",
                "--bootstrap-server",
                "kafka:9092",
                "--topic",
                "oecophylla.user.followed",
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
async fn follow_emits_event_and_rejects_self() {
    let a = cli();
    let b = cli();
    let ua = register(&a).await;
    let ub = register(&b).await;
    let ua_id = ua["user"]["id"].as_str().unwrap();
    let ub_id = ub["user"]["id"].as_str().unwrap();

    // self-follow → 400
    let r = a
        .post(format!("{USER}/api/v1/users/{ua_id}/follow"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::BAD_REQUEST);

    // get offset before follow
    let start_offset = kafka_current_offset();

    // a follows b
    let r = a
        .post(format!("{USER}/api/v1/users/{ub_id}/follow"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::CREATED);

    // verify event landed — use docker exec to consume inside the kafka network
    let body = kafka_consume_one(start_offset);
    assert_eq!(body["data"]["follower_id"], ua_id);
    assert_eq!(body["data"]["followee_id"], ub_id);
}

#[tokio::test]
async fn put_profile_non_owner_forbidden() {
    let a = cli();
    let b = cli();
    let _ua = register(&a).await;
    let ub = register(&b).await;
    let ub_id = ub["user"]["id"].as_str().unwrap();
    let r = a
        .put(format!("{USER}/api/v1/users/{ub_id}"))
        .json(&json!({ "display_name": "hax" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::FORBIDDEN);
}
