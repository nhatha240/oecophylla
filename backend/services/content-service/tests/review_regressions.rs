#![allow(dead_code)]
#[path = "../src/cursor.rs"]
mod cursor;
#[path = "../src/handlers.rs"]
mod handlers;
#[path = "../src/repo.rs"]
mod repo;
#[path = "../src/state.rs"]
mod state;
#[path = "../../../tests/support/review.rs"]
mod support;
#[path = "../src/update.rs"]
mod update;

use axum::{routing::get, Router};
use common::models::{PostStatus, UserRole};
use reqwest::{Client, StatusCode};

#[tokio::test]
async fn unpublished_posts_are_visible_only_to_owner_or_admin() {
    let (db, redis, cfg) = support::setup().await;
    let owner = support::user(&db, UserRole::User).await;
    let other = support::user(&db, UserRole::User).await;
    let admin = support::user(&db, UserRole::Admin).await;
    let app = Router::new()
        .route("/api/v1/posts/{id}", get(handlers::get_one))
        .with_state(state::AppState {
            db: db.clone(),
            redis,
            kafka: common::kafka::Producer::new("").unwrap(),
            cfg: cfg.clone(),
            legacy_view_counter_enabled: false,
        });
    let (base, task) = support::serve(app).await;
    let client = Client::new();
    let mut actual = Vec::new();
    let mut expected = Vec::new();
    for status in [
        PostStatus::Published,
        PostStatus::Pending,
        PostStatus::Hidden,
        PostStatus::Flagged,
    ] {
        let post = repo::insert(&db, owner, "review visibility", &[], &[], &[], status)
            .await
            .unwrap();
        for viewer in [
            None,
            Some((other, UserRole::User)),
            Some((owner, UserRole::User)),
            Some((admin, UserRole::Admin)),
        ] {
            let mut request = client.get(format!("{base}/api/v1/posts/{}", post.id));
            if let Some((id, role)) = viewer {
                request = request.header("cookie", support::cookie(&cfg, id, role));
            }
            actual.push(request.send().await.unwrap().status());
            expected.push(
                if status == PostStatus::Published
                    || viewer.is_some_and(|(id, role)| id == owner || role == UserRole::Admin)
                {
                    StatusCode::OK
                } else {
                    StatusCode::NOT_FOUND
                },
            );
        }
    }
    task.abort();
    assert_eq!(
        actual, expected,
        "published/pending/hidden/flagged by anonymous/other/owner/admin"
    );
}
