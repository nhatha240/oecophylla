//! Pre: docker compose stack up incl. feed-service and recommendation-api.

use std::collections::HashMap;

use common::{auth::issue_access, models::UserRole};
use deadpool_redis::redis::AsyncCommands;
use reqwest::{Client, StatusCode};
use serde_json::Value;
use sqlx::{PgPool, Row, postgres::PgPoolOptions};
use uuid::Uuid;

const ENVOY: &str = "http://localhost:8080";
const JWT_SECRET: &str = "CHANGE_ME__min_32_chars__use_openssl_rand_hex_32";

fn database_url() -> String {
    std::env::var("TEST_DATABASE_URL").unwrap_or_else(|_| {
        "postgres://oecophylla:CHANGE_ME__use_openssl_rand_base64_24@localhost:5432/oecophylla"
            .into()
    })
}

fn redis_url() -> String {
    std::env::var("TEST_REDIS_URL")
        .unwrap_or_else(|_| "redis://:CHANGE_ME__use_openssl_rand_base64_24@localhost:6379".into())
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
        r#"
        INSERT INTO users (id, username, email, password_hash, role)
        VALUES ($1, $2, $3, 'unused-in-test', 'user')
        "#,
    )
    .bind(id)
    .bind(format!("{label}_{}", id.simple()))
    .bind(format!("{label}_{}@example.test", id.simple()))
    .execute(db)
    .await
    .expect("insert test user");
}

async fn insert_post(db: &PgPool, id: Uuid, author_id: Uuid, offset_seconds: i32) {
    sqlx::query(
        r#"
        INSERT INTO posts (
            id, author_id, content, topics, safety_score, status, created_at
        )
        VALUES (
            $1, $2, $3, ARRAY['ai']::text[], 1.0, 'published',
            NOW() + make_interval(secs => $4)
        )
        "#,
    )
    .bind(id)
    .bind(author_id)
    .bind(format!("P1-T1 impression fixture {id}"))
    .bind(offset_seconds)
    .execute(db)
    .await
    .expect("insert test post");
}

fn authenticated_client(user_id: Uuid) -> Client {
    let token = issue_access(JWT_SECRET.as_bytes(), 600, user_id, UserRole::User)
        .expect("issue test access token");
    Client::builder()
        .default_headers({
            let mut headers = reqwest::header::HeaderMap::new();
            headers.insert(
                reqwest::header::COOKIE,
                format!("oec_access={token}").parse().unwrap(),
            );
            headers
        })
        .build()
        .unwrap()
}

async fn get_feed(client: &Client, query: &str) -> (StatusCode, Value) {
    let response = client
        .get(format!("{ENVOY}/api/v1/feed?{query}"))
        .send()
        .await
        .expect("feed request");
    let status = response.status();
    let body = response.json().await.expect("feed JSON response");
    (status, body)
}

async fn impression_rows(db: &PgPool, request_id: Uuid) -> Vec<ImpressionRow> {
    sqlx::query(
        r#"
        SELECT
            id, request_id, user_id, post_id, position, feed_source,
            candidate_source, score, model_version, feature_snapshot::text AS snapshot
        FROM recommendation_impressions
        WHERE request_id = $1
        ORDER BY position
        "#,
    )
    .bind(request_id)
    .fetch_all(db)
    .await
    .expect("select impressions")
    .into_iter()
    .map(|row| ImpressionRow {
        id: row.get("id"),
        request_id: row.get("request_id"),
        user_id: row.get("user_id"),
        post_id: row.get("post_id"),
        position: row.get("position"),
        feed_source: row.get("feed_source"),
        candidate_source: row.get("candidate_source"),
        score: row.get("score"),
        model_version: row.get("model_version"),
        snapshot: serde_json::from_str(row.get::<&str, _>("snapshot")).unwrap(),
    })
    .collect()
}

#[derive(Debug)]
struct ImpressionRow {
    id: Uuid,
    request_id: Uuid,
    user_id: Uuid,
    post_id: Uuid,
    position: i16,
    feed_source: String,
    candidate_source: String,
    score: Option<f32>,
    model_version: String,
    snapshot: Value,
}

fn assert_response_impressions(body: &Value, expected_len: usize, context: &str) -> Uuid {
    let request_id = Uuid::parse_str(body["request_id"].as_str().expect("request_id string"))
        .expect("request_id UUID");
    let items = body["items"].as_array().expect("items array");
    assert_eq!(
        items.len(),
        expected_len,
        "unexpected {context} response: {body}"
    );
    for (position, item) in items.iter().enumerate() {
        assert_eq!(item["position"], position);
        assert!(
            Uuid::parse_str(
                item["impression_id"]
                    .as_str()
                    .expect("impression_id string")
            )
            .is_ok()
        );
    }
    request_id
}

#[tokio::test]
async fn served_impressions_are_batched_after_hydration_and_fail_open() {
    let db = test_pool().await;
    let author_id = Uuid::now_v7();
    let viewer_id = Uuid::now_v7();
    insert_user(&db, author_id, "impression_author").await;
    insert_user(&db, viewer_id, "impression_viewer").await;

    let post_ids = [Uuid::now_v7(), Uuid::now_v7(), Uuid::now_v7()];
    for (offset, post_id) in post_ids.iter().enumerate() {
        insert_post(&db, *post_id, author_id, 100 + offset as i32).await;
    }
    sqlx::query("INSERT INTO follows (follower_id, followee_id) VALUES ($1, $2)")
        .bind(viewer_id)
        .bind(author_id)
        .execute(&db)
        .await
        .unwrap();

    let client = authenticated_client(viewer_id);
    let (status, first) = get_feed(&client, "limit=3").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(first["model_version"], "heuristic-v1");
    let first_request_id = assert_response_impressions(&first, 3, "personalized");
    let first_rows = impression_rows(&db, first_request_id).await;
    assert_eq!(first_rows.len(), 3);
    for (position, row) in first_rows.iter().enumerate() {
        let response_impression_id =
            Uuid::parse_str(first["items"][position]["impression_id"].as_str().unwrap()).unwrap();
        assert_eq!(row.id, response_impression_id);
        assert_eq!(row.request_id, first_request_id);
        assert_eq!(row.user_id, viewer_id);
        assert_eq!(row.position, position as i16);
        assert_eq!(row.feed_source, "personalized");
        assert_eq!(row.model_version, "heuristic-v1");
        assert_eq!(row.snapshot["schema_version"], "rank-features-v1");
        assert_eq!(row.snapshot["candidate_source"], row.candidate_source);
        assert!(row.score.is_some());
    }

    let hidden_post_id = first["items"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|item| item["id"].as_str())
        .filter_map(|id| Uuid::parse_str(id).ok())
        .find(|id| post_ids.contains(id))
        .expect("personalized response should contain a followed-author fixture post");
    sqlx::query("UPDATE posts SET status = 'hidden' WHERE id = $1")
        .bind(hidden_post_id)
        .execute(&db)
        .await
        .unwrap();

    let (status, cached) = get_feed(&client, "limit=3").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(cached["source"], "cache");
    assert_eq!(cached["model_version"], "heuristic-v1");
    let cached_request_id = assert_response_impressions(&cached, 2, "cached");
    assert_ne!(cached_request_id, first_request_id);
    let cached_rows = impression_rows(&db, cached_request_id).await;
    assert_eq!(cached_rows.len(), 2);
    assert!(cached_rows.iter().all(|row| row.post_id != hidden_post_id));

    let original_snapshots = first_rows
        .iter()
        .map(|row| (row.post_id, row.snapshot.clone()))
        .collect::<HashMap<_, _>>();
    for row in &cached_rows {
        assert_eq!(row.snapshot, original_snapshots[&row.post_id]);
    }

    let (status, following) = get_feed(&client, "mode=following&limit=3").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(following["model_version"], "following-v1");
    let following_request_id = assert_response_impressions(&following, 2, "following");
    let following_rows = impression_rows(&db, following_request_id).await;
    assert!(
        following_rows
            .iter()
            .all(|row| row.feed_source == "following"
                && row.candidate_source == "following"
                && row.snapshot["heuristic_score"].is_null())
    );

    let redis_client = deadpool_redis::redis::Client::open(redis_url()).unwrap();
    let mut redis = redis_client
        .get_multiplexed_async_connection()
        .await
        .unwrap();
    let trending_post_id = cached_rows[0].post_id;
    let _: usize = redis
        .zadd("trending:24h", trending_post_id.to_string(), 1_000_000_f64)
        .await
        .unwrap();
    let (status, trending) = get_feed(&client, "mode=trending&limit=1").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(trending["model_version"], "trending-v1");
    let trending_request_id = assert_response_impressions(&trending, 1, "trending");
    let trending_rows = impression_rows(&db, trending_request_id).await;
    assert_eq!(trending_rows[0].candidate_source, "trending");
    let _: usize = redis
        .zrem("trending:24h", trending_post_id.to_string())
        .await
        .unwrap();

    sqlx::query("DROP TRIGGER IF EXISTS test_fail_impression_insert ON recommendation_impressions")
        .execute(&db)
        .await
        .unwrap();
    sqlx::query(
        r#"
        CREATE OR REPLACE FUNCTION test_fail_selected_impression()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.user_id::text = TG_ARGV[0] THEN
                RAISE EXCEPTION 'forced impression failure';
            END IF;
            RETURN NEW;
        END
        $$
        "#,
    )
    .execute(&db)
    .await
    .unwrap();
    let create_trigger = format!(
        "CREATE TRIGGER test_fail_impression_insert BEFORE INSERT ON recommendation_impressions \
         FOR EACH ROW EXECUTE FUNCTION test_fail_selected_impression('{}')",
        viewer_id
    );
    sqlx::query(sqlx::AssertSqlSafe(create_trigger))
        .execute(&db)
        .await
        .unwrap();

    let (failure_status, failed) = get_feed(&client, "limit=3").await;

    sqlx::query("DROP TRIGGER test_fail_impression_insert ON recommendation_impressions")
        .execute(&db)
        .await
        .unwrap();
    sqlx::query("DROP FUNCTION test_fail_selected_impression()")
        .execute(&db)
        .await
        .unwrap();

    assert_eq!(failure_status, StatusCode::OK);
    let failed_request_id = Uuid::parse_str(failed["request_id"].as_str().unwrap()).unwrap();
    assert!(
        failed["items"]
            .as_array()
            .unwrap()
            .iter()
            .all(|item| item["impression_id"].is_null())
    );
    assert!(impression_rows(&db, failed_request_id).await.is_empty());

    sqlx::query("DELETE FROM users WHERE id = ANY($1::uuid[])")
        .bind(vec![viewer_id, author_id])
        .execute(&db)
        .await
        .unwrap();
}
