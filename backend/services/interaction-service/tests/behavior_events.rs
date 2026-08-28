//! Pre: docker compose stack up with the interaction service routed through Envoy.
//! Run the stack with `BEHAVIOR_VIEW_COUNTER_ENABLED=true` for counter assertions.

use chrono::{Duration, Utc};
use common::{auth::issue_access, models::UserRole};
use reqwest::{Client, StatusCode};
use serde_json::{Value, json};
use sqlx::{PgPool, Row, postgres::PgPoolOptions};
use std::process::Command;
use uuid::Uuid;

const ENVOY: &str = "http://localhost:8080";
const JWT_SECRET: &str = "CHANGE_ME__min_32_chars__use_openssl_rand_hex_32";

fn database_url() -> String {
    std::env::var("TEST_DATABASE_URL").unwrap_or_else(|_| {
        "postgres://oecophylla:CHANGE_ME__use_openssl_rand_base64_24@localhost:5432/oecophylla"
            .into()
    })
}

async fn test_pool() -> PgPool {
    PgPoolOptions::new()
        .max_connections(2)
        .connect(&database_url())
        .await
        .expect("connect test postgres")
}

async fn insert_user(db: &PgPool, id: Uuid, label: &str) {
    sqlx::query(
        "INSERT INTO users (id, username, email, password_hash, role) \
         VALUES ($1, $2, $3, 'unused-in-test', 'user')",
    )
    .bind(id)
    .bind(format!("{label}_{}", id.simple()))
    .bind(format!("{label}_{}@example.test", id.simple()))
    .execute(db)
    .await
    .expect("insert test user");
}

async fn insert_post(db: &PgPool, id: Uuid, author_id: Uuid) {
    sqlx::query(
        "INSERT INTO posts (id, author_id, content, topics, status) \
         VALUES ($1, $2, $3, ARRAY['ai']::text[], 'published')",
    )
    .bind(id)
    .bind(author_id)
    .bind(format!("P1-T2 behavior fixture {id}"))
    .execute(db)
    .await
    .expect("insert test post");
}

async fn insert_impression(db: &PgPool, id: Uuid, user_id: Uuid, post_id: Uuid) {
    sqlx::query(
        r#"
        INSERT INTO recommendation_impressions (
            id, request_id, user_id, post_id, position, feed_source,
            candidate_source, score, model_version, feature_snapshot
        )
        VALUES ($1, $2, $3, $4, 0, 'personalized', 'follow', 1.0,
                'heuristic-v1', '{"schema_version":"rank-features-v1"}'::jsonb)
        "#,
    )
    .bind(id)
    .bind(Uuid::now_v7())
    .bind(user_id)
    .bind(post_id)
    .execute(db)
    .await
    .expect("insert test impression");
}

fn client(user_id: Option<Uuid>) -> Client {
    let mut builder = Client::builder();
    if let Some(user_id) = user_id {
        let token = issue_access(JWT_SECRET.as_bytes(), 600, user_id, UserRole::User)
            .expect("issue test access token");
        let mut headers = reqwest::header::HeaderMap::new();
        headers.insert(
            reqwest::header::COOKIE,
            format!("oec_access={token}").parse().unwrap(),
        );
        builder = builder.default_headers(headers);
    }
    builder.build().unwrap()
}

async fn post_batch(client: &Client, events: Value) -> (StatusCode, Value) {
    let response = client
        .post(format!("{ENVOY}/api/v1/interactions/events/batch"))
        .json(&json!({ "events": events }))
        .send()
        .await
        .expect("behavior batch request");
    let status = response.status();
    let bytes = response
        .bytes()
        .await
        .expect("behavior batch response body");
    let body = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes).expect("behavior batch JSON response")
    };
    (status, body)
}

fn telemetry_event(
    client_event_id: Uuid,
    post_id: Uuid,
    impression_id: Option<Uuid>,
    event_type: &str,
    dwell_ms: Option<i32>,
    metadata: Value,
) -> Value {
    json!({
        "client_event_id": client_event_id,
        "post_id": post_id,
        "impression_id": impression_id,
        "session_id": Uuid::now_v7(),
        "event_type": event_type,
        "dwell_ms": dwell_ms,
        "metadata": metadata,
        "occurred_at": Utc::now(),
    })
}

fn kafka_topic_snapshot() -> String {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let output = Command::new("docker")
        .current_dir(repo_root)
        .args([
            "compose",
            "--env-file",
            ".env.example",
            "-f",
            "compose.yaml",
            "-f",
            "compose.dev.yaml",
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-consumer.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "oecophylla.interactions",
            "--partition",
            "0",
            "--offset",
            "earliest",
            "--max-messages",
            "10000",
            "--timeout-ms",
            "2000",
        ])
        .output()
        .expect("read Kafka interaction topic");
    format!(
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    )
}

#[tokio::test]
async fn behavior_batch_is_authenticated_partial_idempotent_and_append_only() {
    let db = test_pool().await;
    let author_id = Uuid::now_v7();
    let viewer_id = Uuid::now_v7();
    let other_id = Uuid::now_v7();
    let post_id = Uuid::now_v7();
    for (id, label) in [
        (author_id, "behavior_author"),
        (viewer_id, "behavior_viewer"),
        (other_id, "behavior_other"),
    ] {
        insert_user(&db, id, label).await;
    }
    insert_post(&db, post_id, author_id).await;
    let viewer_impression = Uuid::now_v7();
    let other_impression = Uuid::now_v7();
    insert_impression(&db, viewer_impression, viewer_id, post_id).await;
    insert_impression(&db, other_impression, other_id, post_id).await;

    let visible_id = Uuid::now_v7();
    let visible = telemetry_event(
        visible_id,
        post_id,
        Some(viewer_impression),
        "visible",
        None,
        json!({ "viewport_ratio": 0.75 }),
    );
    let (status, _) = post_batch(&client(None), json!([visible.clone()])).await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);

    let mut spoofed_visible = visible;
    spoofed_visible["user_id"] = json!(other_id);
    let invalid_action = telemetry_event(
        Uuid::now_v7(),
        post_id,
        Some(viewer_impression),
        "like",
        None,
        json!({}),
    );
    let mismatched_impression = telemetry_event(
        Uuid::now_v7(),
        post_id,
        Some(other_impression),
        "visible",
        None,
        json!({ "viewport_ratio": 0.8 }),
    );
    let viewer = client(Some(viewer_id));
    let (status, mixed) = post_batch(
        &viewer,
        json!([spoofed_visible, invalid_action, mismatched_impression]),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "mixed response: {mixed}");
    assert_eq!(mixed["accepted"], 1);
    assert_eq!(mixed["duplicate"], 0);
    assert_eq!(mixed["rejected"], 2);
    assert_eq!(mixed["errors"][0]["index"], 1);
    assert_eq!(mixed["errors"][1]["index"], 2);

    let stored_user: Uuid =
        sqlx::query_scalar("SELECT user_id FROM behavior_events WHERE client_event_id = $1")
            .bind(visible_id)
            .fetch_one(&db)
            .await
            .unwrap();
    assert_eq!(
        stored_user, viewer_id,
        "payload user_id must never win over JWT"
    );

    let view_id = Uuid::now_v7();
    let qualified_view = telemetry_event(
        view_id,
        post_id,
        Some(viewer_impression),
        "view",
        Some(10_000),
        json!({ "continuous_visible_ms": 10_000, "trigger": "feed" }),
    );
    let (status, first_view) = post_batch(&viewer, json!([qualified_view.clone()])).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(first_view["accepted"], 1);
    let (status, retried_view) = post_batch(&viewer, json!([qualified_view])).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(retried_view["accepted"], 0);
    assert_eq!(retried_view["duplicate"], 1);

    let (view_count, stored_views): (i64, i64) = sqlx::query_as(
        "SELECT p.view_count, count(e.id) \
         FROM posts p LEFT JOIN behavior_events e \
           ON e.post_id = p.id AND e.client_event_id = $2 \
         WHERE p.id = $1 GROUP BY p.view_count",
    )
    .bind(post_id)
    .bind(view_id)
    .fetch_one(&db)
    .await
    .unwrap();
    assert_eq!(
        view_count, 1,
        "retry must not increment the view counter twice"
    );
    assert_eq!(stored_views, 1);

    let under_guardrail_id = Uuid::now_v7();
    let under_guardrail_view = telemetry_event(
        under_guardrail_id,
        post_id,
        Some(viewer_impression),
        "view",
        Some(5_000),
        json!({ "continuous_visible_ms": 5_000, "trigger": "feed" }),
    );
    let (status, under_guardrail) = post_batch(&viewer, json!([under_guardrail_view])).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(under_guardrail["accepted"], 1);
    let stored_dwell: i32 =
        sqlx::query_scalar("SELECT dwell_ms FROM behavior_events WHERE client_event_id = $1")
            .bind(under_guardrail_id)
            .fetch_one(&db)
            .await
            .unwrap();
    assert_eq!(stored_dwell, 5_000, "sub-positive view remains telemetry");
    let kafka_events = kafka_topic_snapshot();
    assert!(
        kafka_events.contains(&view_id.to_string()),
        "positive view should publish viewed envelope; Kafka output: {kafka_events}"
    );
    assert!(
        !kafka_events.contains(&under_guardrail_id.to_string()),
        "view below positive dwell guardrail must not publish a preference signal"
    );

    let old_dwell_id = Uuid::now_v7();
    let mut old_dwell = telemetry_event(
        old_dwell_id,
        post_id,
        None,
        "dwell",
        Some(12_000),
        json!({ "trigger": "page_hidden" }),
    );
    old_dwell["occurred_at"] = json!(Utc::now() - Duration::hours(48));
    let unknown_metadata = telemetry_event(
        Uuid::now_v7(),
        post_id,
        None,
        "click",
        None,
        json!({ "raw_cookie": "must-not-be-stored" }),
    );
    let (status, validation) = post_batch(&viewer, json!([old_dwell, unknown_metadata])).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(validation["accepted"], 1);
    assert_eq!(validation["rejected"], 1);
    let (occurred_at, ingested_at): (chrono::DateTime<Utc>, chrono::DateTime<Utc>) =
        sqlx::query_as(
            "SELECT occurred_at, ingested_at FROM behavior_events WHERE client_event_id = $1",
        )
        .bind(old_dwell_id)
        .fetch_one(&db)
        .await
        .unwrap();
    assert!(occurred_at >= ingested_at - Duration::hours(24) - Duration::seconds(1));

    let too_many = (0..101)
        .map(|_| {
            telemetry_event(
                Uuid::now_v7(),
                post_id,
                None,
                "visible",
                None,
                json!({ "viewport_ratio": 0.8 }),
            )
        })
        .collect::<Vec<_>>();
    let (status, _) = post_batch(&viewer, json!(too_many)).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    for path in ["like", "like"] {
        viewer
            .post(format!("{ENVOY}/api/v1/posts/{post_id}/{path}"))
            .send()
            .await
            .unwrap();
    }
    for path in ["like", "like"] {
        viewer
            .delete(format!("{ENVOY}/api/v1/posts/{post_id}/{path}"))
            .send()
            .await
            .unwrap();
    }
    viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/save"))
        .send()
        .await
        .unwrap();
    viewer
        .delete(format!("{ENVOY}/api/v1/posts/{post_id}/save"))
        .send()
        .await
        .unwrap();
    viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/share"))
        .send()
        .await
        .unwrap();
    viewer
        .delete(format!("{ENVOY}/api/v1/posts/{post_id}/share"))
        .send()
        .await
        .unwrap();
    viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/hide"))
        .send()
        .await
        .unwrap();
    viewer
        .delete(format!("{ENVOY}/api/v1/posts/{post_id}/hide"))
        .send()
        .await
        .unwrap();
    let report = viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();
    assert_eq!(report.status(), StatusCode::CREATED);
    let duplicate_report = viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();
    assert_eq!(duplicate_report.status(), StatusCode::CONFLICT);
    let comment = viewer
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/comments"))
        .json(&json!({ "content": "append-only behavior comment" }))
        .send()
        .await
        .unwrap();
    assert_eq!(comment.status(), StatusCode::OK);

    let action_rows = sqlx::query(
        "SELECT event_type, count(*) AS count FROM behavior_events \
         WHERE user_id = $1 AND post_id = $2 \
           AND event_type IN ( \
             'like', 'unlike', 'save', 'unsave', 'share', 'unshare', \
             'hide', 'unhide', 'report', 'comment' \
           ) \
         GROUP BY event_type",
    )
    .bind(viewer_id)
    .bind(post_id)
    .fetch_all(&db)
    .await
    .unwrap();
    let action_counts = action_rows
        .into_iter()
        .map(|row| {
            (
                row.get::<String, _>("event_type"),
                row.get::<i64, _>("count"),
            )
        })
        .collect::<std::collections::HashMap<_, _>>();
    assert_eq!(action_counts.get("like"), Some(&1));
    assert_eq!(action_counts.get("unlike"), Some(&1));
    assert_eq!(action_counts.get("save"), Some(&1));
    assert_eq!(action_counts.get("unsave"), Some(&1));
    assert_eq!(action_counts.get("share"), Some(&1));
    assert_eq!(action_counts.get("unshare"), Some(&1));
    assert_eq!(action_counts.get("hide"), Some(&1));
    assert_eq!(action_counts.get("unhide"), Some(&1));
    assert_eq!(action_counts.get("report"), Some(&1));
    assert_eq!(action_counts.get("comment"), Some(&1));

    sqlx::query("DELETE FROM users WHERE id = ANY($1::uuid[])")
        .bind(vec![viewer_id, other_id, author_id])
        .execute(&db)
        .await
        .unwrap();
}

#[tokio::test]
#[ignore = "requires Kafka stopped after interaction-service has started"]
async fn kafka_failure_keeps_committed_behavior_event() {
    let db = test_pool().await;
    let author_id = Uuid::now_v7();
    let viewer_id = Uuid::now_v7();
    let post_id = Uuid::now_v7();
    insert_user(&db, author_id, "kafka_fail_author").await;
    insert_user(&db, viewer_id, "kafka_fail_viewer").await;
    insert_post(&db, post_id, author_id).await;

    let client_event_id = Uuid::now_v7();
    let qualified_view = telemetry_event(
        client_event_id,
        post_id,
        None,
        "view",
        Some(10_000),
        json!({ "continuous_visible_ms": 10_000, "trigger": "feed" }),
    );
    let (status, response) = post_batch(&client(Some(viewer_id)), json!([qualified_view])).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(response["accepted"], 1);
    let stored: i64 =
        sqlx::query_scalar("SELECT count(*) FROM behavior_events WHERE client_event_id = $1")
            .bind(client_event_id)
            .fetch_one(&db)
            .await
            .unwrap();
    assert_eq!(
        stored, 1,
        "Kafka availability must not control DB durability"
    );

    sqlx::query("DELETE FROM users WHERE id = ANY($1::uuid[])")
        .bind(vec![viewer_id, author_id])
        .execute(&db)
        .await
        .unwrap();
}
