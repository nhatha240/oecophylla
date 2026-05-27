//! Pre: docker compose stack up incl. moderation-service. Hits moderation-service
//! directly because Envoy does not route `/admin/*` until Phase 3 Task 19. Use
//! `MODERATION_DIRECT_URL` to override (default `http://localhost:8006`).
//!
//! Promotes a freshly registered user to admin by issuing a `docker compose exec
//! postgres psql` UPDATE — there is no admin self-service endpoint by design.

use reqwest::{Client, StatusCode};
use serde_json::{json, Value};
use std::process::Command;

const ENVOY: &str = "http://localhost:8080";

fn moderation_url() -> String {
    std::env::var("MODERATION_DIRECT_URL").unwrap_or_else(|_| "http://localhost:8006".into())
}

fn cli() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}

/// Suffix that's guaranteed username-safe (lowercase hex, no leading digit issues
/// thanks to the `u` prefix). UUIDv7 "simple" form is 32 hex chars; we use the
/// trailing 10 to stay under the 50-char username limit.
fn rand_suffix() -> String {
    let s = uuid::Uuid::now_v7().simple().to_string();
    s[22..].to_string()
}

async fn register(c: &Client) -> (String, Value) {
    let suffix = rand_suffix();
    let username = format!("u{suffix}");
    let email = format!("{suffix}@e.com");
    let r = c
        .post(format!("{ENVOY}/api/v1/auth/register"))
        .json(&json!({
            "username": username,
            "email": email,
            "password": "Password!123"
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(
        r.status(),
        200,
        "register failed: {}",
        r.text().await.unwrap()
    );
    let body: Value = r.json().await.unwrap();
    (username, body)
}

async fn login(c: &Client, username: &str) {
    let r = c
        .post(format!("{ENVOY}/api/v1/auth/login"))
        .json(&json!({
            "email_or_username": username,
            "password": "Password!123"
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "login failed: {}", r.text().await.unwrap());
}

async fn create_post(c: &Client, content: &str) -> String {
    let r = c
        .post(format!("{ENVOY}/api/v1/posts"))
        .json(&json!({ "content": content }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "create_post: {}", r.text().await.unwrap());
    let v: Value = r.json().await.unwrap();
    v["id"].as_str().unwrap().to_string()
}

async fn submit_report(c: &Client, post_id: &str) {
    let r = c
        .post(format!("{ENVOY}/api/v1/posts/{post_id}/report"))
        .json(&json!({ "reason": "spam" }))
        .send()
        .await
        .unwrap();
    assert_eq!(
        r.status(),
        StatusCode::CREATED,
        "report: {:?}",
        r.text().await.unwrap()
    );
}

/// Runs `psql` inside the postgres container. We use this rather than wiring an
/// sqlx pool into the test because the test only ever needs a couple of one-off
/// queries — keeping it out-of-process means the test doesn't need DB credentials
/// or a network route from the host into the docker network.
fn psql(sql: &str) -> String {
    let out = Command::new("docker")
        .args([
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "oecophylla",
            "-d",
            "oecophylla",
            "-tA",
            "-c",
            sql,
        ])
        .output()
        .expect("docker exec psql failed");
    if !out.status.success() {
        panic!(
            "psql failed: {}\nstderr: {}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr),
        );
    }
    String::from_utf8_lossy(&out.stdout).trim().to_string()
}

fn promote_to_admin(username: &str) {
    psql(&format!(
        "UPDATE users SET role = 'admin' WHERE username = '{username}'"
    ));
}

/// Pull the most-recent pending report id for a given post. The interaction
/// service inserts reports via `INSERT ... RETURNING id` but the HTTP response
/// is 201 with no body, so we look the row up by post here.
fn latest_report_for_post(post_id: &str) -> String {
    psql(&format!(
        "SELECT id FROM reports WHERE post_id = '{post_id}' ORDER BY created_at DESC LIMIT 1"
    ))
}

fn report_status(report_id: &str) -> String {
    psql(&format!(
        "SELECT status::text FROM reports WHERE id = '{report_id}'"
    ))
}

fn post_status(post_id: &str) -> String {
    psql(&format!(
        "SELECT status::text FROM posts WHERE id = '{post_id}'"
    ))
}

fn user_is_active(user_id: &str) -> String {
    psql(&format!(
        "SELECT is_active FROM users WHERE id = '{user_id}'"
    ))
}

fn audit_count_for_report(report_id: &str) -> i64 {
    let s = psql(&format!(
        "SELECT COUNT(*) FROM audit_logs WHERE report_id = '{report_id}'"
    ));
    s.parse().unwrap_or(0)
}

fn poll_kafka_for(event_type: &str, expected_report_id: &str) -> String {
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
            "oecophylla.moderation.action",
            "--from-beginning",
            "--max-messages",
            "50",
            "--timeout-ms",
            "5000",
        ])
        .output()
        .expect("docker exec kafka failed");
    let body = String::from_utf8_lossy(&out.stdout).to_string();
    assert!(
        body.contains(&format!("\"event_type\":\"{event_type}\"")),
        "expected event_type {event_type} in kafka stdout, got: {body}"
    );
    assert!(
        body.contains(expected_report_id),
        "expected report_id {expected_report_id} in kafka stdout, got: {body}"
    );
    body
}

/// Set up: register an author, register a reporter, reporter reports the author's
/// post. Returns (author_client, post_id, report_id, author_user_id).
async fn setup_report() -> (Client, String, String, String) {
    let author = cli();
    let (_a_name, a_info) = register(&author).await;
    let author_id = a_info["user"]["id"]
        .as_str()
        .expect("register response should include user.id")
        .to_string();
    let post_id = create_post(&author, "moderation smoke target").await;

    let reporter = cli();
    let _ = register(&reporter).await;
    submit_report(&reporter, &post_id).await;

    let report_id = latest_report_for_post(&post_id);
    assert!(
        !report_id.is_empty(),
        "expected a report row for post {post_id}"
    );
    (author, post_id, report_id, author_id)
}

async fn admin_session() -> Client {
    let c = cli();
    let (username, _) = register(&c).await;
    promote_to_admin(&username);
    // Re-login so the new JWT carries `role = admin`.
    login(&c, &username).await;
    c
}

// ---------- tests ----------

#[tokio::test]
async fn non_admin_gets_403() {
    let (author, _post_id, report_id, _author_id) = setup_report().await;
    let r = author
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "dismiss" }))
        .send()
        .await
        .unwrap();
    assert_eq!(
        r.status(),
        StatusCode::FORBIDDEN,
        "non-admin must be 403, got {}: {}",
        r.status(),
        r.text().await.unwrap()
    );
}

#[tokio::test]
async fn admin_dismiss_resolves_ok_and_emits_kafka() {
    let (_author, _post_id, report_id, _author_id) = setup_report().await;
    let admin = admin_session().await;

    let r = admin
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "dismiss", "note": "false positive" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "dismiss: {}", r.text().await.unwrap());
    let body: Value = r.json().await.unwrap();
    assert_eq!(body["status"], "resolved_ok");

    assert_eq!(report_status(&report_id), "resolved_ok");
    assert_eq!(audit_count_for_report(&report_id), 1);
    poll_kafka_for("report_dismissed", &report_id);
}

#[tokio::test]
async fn admin_hide_post_flips_post_status_and_emits_kafka() {
    let (_author, post_id, report_id, _author_id) = setup_report().await;
    let admin = admin_session().await;

    let r = admin
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "hide_post" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "hide_post: {}", r.text().await.unwrap());

    assert_eq!(report_status(&report_id), "resolved_hidden");
    assert_eq!(post_status(&post_id), "hidden");
    assert_eq!(audit_count_for_report(&report_id), 1);
    poll_kafka_for("post_hidden", &report_id);
}

#[tokio::test]
async fn admin_ban_author_deactivates_user_and_emits_kafka() {
    let (_author, _post_id, report_id, author_id) = setup_report().await;
    let admin = admin_session().await;

    let r = admin
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "ban_author", "note": "repeat offender" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200, "ban_author: {}", r.text().await.unwrap());

    assert_eq!(report_status(&report_id), "resolved_warned");
    assert_eq!(user_is_active(&author_id), "f");
    assert_eq!(audit_count_for_report(&report_id), 1);
    poll_kafka_for("author_banned", &report_id);
}

#[tokio::test]
async fn resolving_already_resolved_report_returns_409() {
    let (_author, _post_id, report_id, _author_id) = setup_report().await;
    let admin = admin_session().await;

    let r = admin
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "dismiss" }))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);

    // Second call on the same report.
    let r = admin
        .post(format!(
            "{}/admin/reports/{report_id}/resolve",
            moderation_url()
        ))
        .json(&json!({ "action": "dismiss" }))
        .send()
        .await
        .unwrap();
    assert_eq!(
        r.status(),
        StatusCode::CONFLICT,
        "expected 409 on second resolve, got {}: {}",
        r.status(),
        r.text().await.unwrap()
    );
}
