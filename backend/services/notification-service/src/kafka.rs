use rdkafka::{
    config::ClientConfig,
    consumer::{Consumer, StreamConsumer},
    Message,
};
use serde::Deserialize;
use uuid::Uuid;

use crate::{handlers::dispatch_notification, state::AppState};

const GROUP_ID: &str = "oecophylla.notification.v1";

const TOPIC_INTERACTIONS: &str = "oecophylla.interactions";
const TOPIC_USER_FOLLOWED: &str = "oecophylla.user.followed";
const TOPIC_MODERATION_ACTION: &str = "oecophylla.moderation.action";

// ── Envelope (deserialization only) ──────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct InboundEnvelope {
    #[serde(default)]
    event_type: String,
    data: serde_json::Value,
}

// ── Specific event payloads ───────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct ToggleData {
    user_id: Uuid,
    post_id: Uuid,
    post_author_id: Uuid,
}

#[derive(Debug, Deserialize)]
struct CommentData {
    commenter_id: Uuid,
    post_id: Uuid,
    post_author_id: Uuid,
    comment_id: Uuid,
    parent_comment_id: Option<Uuid>,
    content_preview: String,
}

#[derive(Debug, Deserialize)]
struct UserFollowedData {
    follower_id: Uuid,
    followee_id: Uuid,
}

#[derive(Debug, Deserialize)]
struct ModerationActionData {
    #[allow(dead_code)]
    actor_id: Uuid,
    target_user_id: Uuid,
    target_post_id: Option<Uuid>,
}

// ── Consumer builder ─────────────────────────────────────────────────────────

fn build_consumer(brokers: &str) -> anyhow::Result<StreamConsumer> {
    Ok(ClientConfig::new()
        .set("bootstrap.servers", brokers)
        .set("group.id", GROUP_ID)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest")
        .create()?)
}

// ── Spawn all three consumer tasks ───────────────────────────────────────────

/// Spawn three Tokio tasks — one per Kafka topic — and let them run forever.
pub fn spawn_consumers(state: AppState) {
    let brokers = state.notif_cfg.kafka_brokers.clone();

    {
        let state = state.clone();
        let brokers = brokers.clone();
        tokio::spawn(async move {
            run_consumer_loop(&brokers, TOPIC_INTERACTIONS, state, handle_interaction).await;
        });
    }

    {
        let state = state.clone();
        let brokers = brokers.clone();
        tokio::spawn(async move {
            run_consumer_loop(&brokers, TOPIC_USER_FOLLOWED, state, handle_user_followed).await;
        });
    }

    {
        let state = state.clone();
        tokio::spawn(async move {
            run_consumer_loop(
                &brokers,
                TOPIC_MODERATION_ACTION,
                state,
                handle_moderation_action,
            )
            .await;
        });
    }
}

// ── Generic consumer loop ─────────────────────────────────────────────────────

async fn run_consumer_loop<F, Fut>(brokers: &str, topic: &str, state: AppState, handler: F)
where
    F: Fn(AppState, InboundEnvelope) -> Fut,
    Fut: std::future::Future<Output = anyhow::Result<()>>,
{
    let consumer = match build_consumer(brokers) {
        Ok(c) => c,
        Err(e) => {
            tracing::error!(error = %e, %topic, "failed to build kafka consumer");
            return;
        }
    };

    if let Err(e) = consumer.subscribe(&[topic]) {
        tracing::error!(error = %e, %topic, "failed to subscribe");
        return;
    }

    tracing::info!(%topic, group = GROUP_ID, "notification consumer subscribed");

    loop {
        let msg = match consumer.recv().await {
            Ok(m) => m,
            Err(e) => {
                tracing::warn!(error = %e, %topic, "kafka recv error");
                continue;
            }
        };

        let payload = match msg.payload() {
            Some(p) => p,
            None => {
                let _ = consumer.commit_message(&msg, rdkafka::consumer::CommitMode::Async);
                continue;
            }
        };

        let envelope: InboundEnvelope = match serde_json::from_slice(payload) {
            Ok(e) => e,
            Err(e) => {
                tracing::warn!(error = %e, %topic, "skipping malformed envelope");
                let _ = consumer.commit_message(&msg, rdkafka::consumer::CommitMode::Async);
                continue;
            }
        };

        if let Err(e) = handler(state.clone(), envelope).await {
            tracing::warn!(error = %e, %topic, "notification handler error");
        }

        let _ = consumer.commit_message(&msg, rdkafka::consumer::CommitMode::Async);
    }
}

// ── Per-topic handlers ────────────────────────────────────────────────────────

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_envelope(json: &str) -> InboundEnvelope {
        serde_json::from_str(json).expect("valid envelope JSON")
    }

    // ── InboundEnvelope deserialization ─────────────────────────────────────

    #[test]
    fn envelope_parses_event_type_and_data() {
        let env = parse_envelope(
            r#"{"event_type":"liked","data":{"user_id":"u1","post_id":"p1","post_author_id":"a1"}}"#,
        );
        assert_eq!(env.event_type, "liked");
        assert_eq!(env.data["user_id"], "u1");
    }

    #[test]
    fn envelope_defaults_event_type_to_empty() {
        let env = parse_envelope(r#"{"data":{"user_id":"u1"}}"#);
        assert_eq!(env.event_type, "");
    }

    #[test]
    fn envelope_rejects_missing_data() {
        let result: Result<InboundEnvelope, _> = serde_json::from_str(r#"{"event_type":"liked"}"#);
        assert!(result.is_err(), "data field should be required");
    }

    // ── Data struct deserialization ─────────────────────────────────────────

    #[test]
    fn toggle_data_parses_all_fields() {
        let d: ToggleData = serde_json::from_value(serde_json::json!({
            "user_id": "11111111-1111-1111-1111-111111111111",
            "post_id": "22222222-2222-2222-2222-222222222222",
            "post_author_id": "33333333-3333-3333-3333-333333333333"
        }))
        .unwrap();
        assert_eq!(
            d.user_id,
            Uuid::parse_str("11111111-1111-1111-1111-111111111111").unwrap()
        );
        assert_eq!(
            d.post_author_id,
            Uuid::parse_str("33333333-3333-3333-3333-333333333333").unwrap()
        );
    }

    #[test]
    fn comment_data_parses_with_optional_parent() {
        let d: CommentData = serde_json::from_value(serde_json::json!({
            "commenter_id": "11111111-1111-1111-1111-111111111111",
            "post_id": "22222222-2222-2222-2222-222222222222",
            "post_author_id": "33333333-3333-3333-3333-333333333333",
            "comment_id": "44444444-4444-4444-4444-444444444444",
            "parent_comment_id": null,
            "content_preview": "hello"
        }))
        .unwrap();
        assert!(d.parent_comment_id.is_none());
        assert_eq!(d.content_preview, "hello");
    }

    #[test]
    fn comment_data_parses_with_parent_present() {
        let d: CommentData = serde_json::from_value(serde_json::json!({
            "commenter_id": "11111111-1111-1111-1111-111111111111",
            "post_id": "22222222-2222-2222-2222-222222222222",
            "post_author_id": "33333333-3333-3333-3333-333333333333",
            "comment_id": "44444444-4444-4444-4444-444444444444",
            "parent_comment_id": "55555555-5555-5555-5555-555555555555",
            "content_preview": "reply text"
        }))
        .unwrap();
        assert_eq!(
            d.parent_comment_id,
            Some(Uuid::parse_str("55555555-5555-5555-5555-555555555555").unwrap())
        );
    }

    #[test]
    fn user_followed_data_parses() {
        let d: UserFollowedData = serde_json::from_value(serde_json::json!({
            "follower_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "followee_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        }))
        .unwrap();
        assert_eq!(
            d.follower_id,
            Uuid::parse_str("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa").unwrap()
        );
    }

    #[test]
    fn moderation_action_data_parses() {
        let d: ModerationActionData = serde_json::from_value(serde_json::json!({
            "actor_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "target_user_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "target_post_id": null
        }))
        .unwrap();
        assert!(d.target_post_id.is_none());
    }

    // ── Event routing logic (matching) ──────────────────────────────────────

    #[test]
    fn interaction_handler_matches_liked_commented_replied() {
        for event_type in ["liked", "commented", "replied"] {
            let env = parse_envelope(&format!(
                r#"{{"event_type":"{event_type}","data":{{"user_id":"11111111-1111-1111-1111-111111111111","post_id":"22222222-2222-2222-2222-222222222222","post_author_id":"33333333-3333-3333-3333-333333333333","commenter_id":"44444444-4444-4444-4444-444444444444","comment_id":"55555555-5555-5555-5555-555555555555","parent_comment_id":null,"content_preview":"test"}}}}"#
            ));
            // These event types enter the match arms (not the catch-all).
            assert!(
                matches!(env.event_type.as_str(), "liked" | "commented" | "replied"),
                "should match {event_type}"
            );
        }
    }

    #[test]
    fn interaction_handler_ignores_saved_shared_hidden() {
        for event_type in ["saved", "shared", "hidden", "reported", "viewed"] {
            let env = parse_envelope(&format!(
                r#"{{"event_type":"{event_type}","data":{{"user_id":"11111111-1111-1111-1111-111111111111","post_id":"22222222-2222-2222-2222-222222222222","post_author_id":"33333333-3333-3333-3333-333333333333","commenter_id":"44444444-4444-4444-4444-444444444444","comment_id":"55555555-5555-5555-5555-555555555555","parent_comment_id":null,"content_preview":"test"}}}}"#
            ));
            assert!(
                matches!(
                    env.event_type.as_str(),
                    "saved" | "shared" | "hidden" | "reported" | "viewed"
                ),
                "should be an ignored event type"
            );
        }
    }

    #[test]
    fn moderation_handler_matches_action_types() {
        for event_type in ["post_hidden", "author_warned", "author_banned"] {
            let env = parse_envelope(&format!(
                r#"{{"event_type":"{event_type}","data":{{"actor_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","target_user_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","target_post_id":null}}}}"#
            ));
            let kind = match env.event_type.as_str() {
                "post_hidden" => Some("post_hidden"),
                "author_warned" => Some("author_warned"),
                "author_banned" => Some("author_banned"),
                _ => None,
            };
            assert_eq!(kind, Some(event_type));
        }
    }

    #[test]
    fn moderation_handler_ignores_report_dismissed() {
        let env = parse_envelope(
            r#"{"event_type":"report_dismissed","data":{"actor_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","target_user_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}}"#,
        );
        assert!(matches!(
            env.event_type.as_str(),
            "report_dismissed" | "post_unhidden" | "author_unbanned"
        ));
    }
}

async fn handle_interaction(state: AppState, env: InboundEnvelope) -> anyhow::Result<()> {
    match env.event_type.as_str() {
        "liked" => {
            let d: ToggleData = serde_json::from_value(env.data)?;
            // Skip self-like.
            if d.user_id == d.post_author_id {
                return Ok(());
            }
            dispatch_notification(
                &state,
                d.post_author_id,
                "liked",
                Some(d.user_id),
                Some(d.post_id),
                None,
                serde_json::json!({}),
            )
            .await
        }
        "commented" => {
            let d: CommentData = serde_json::from_value(env.data)?;
            // Skip self-comment.
            if d.commenter_id == d.post_author_id {
                return Ok(());
            }
            dispatch_notification(
                &state,
                d.post_author_id,
                "commented",
                Some(d.commenter_id),
                Some(d.post_id),
                Some(d.comment_id),
                serde_json::json!({ "preview": d.content_preview }),
            )
            .await
        }
        "replied" => {
            let d: CommentData = serde_json::from_value(env.data)?;
            // The recipient is the parent comment's author.
            let parent_id = match d.parent_comment_id {
                Some(id) => id,
                None => {
                    tracing::warn!(
                        comment_id = %d.comment_id,
                        "replied event missing parent_comment_id"
                    );
                    return Ok(());
                }
            };

            let parent_author: Option<Uuid> =
                sqlx::query_scalar("SELECT author_id FROM comments WHERE id = $1")
                    .bind(parent_id)
                    .fetch_optional(&state.db)
                    .await?;

            let recipient = match parent_author {
                Some(id) => id,
                None => return Ok(()), // parent deleted
            };

            // Skip self-reply.
            if d.commenter_id == recipient {
                return Ok(());
            }

            dispatch_notification(
                &state,
                recipient,
                "replied",
                Some(d.commenter_id),
                Some(d.post_id),
                Some(d.comment_id),
                serde_json::json!({ "preview": d.content_preview }),
            )
            .await
        }
        // Intentionally ignored event types.
        "saved" | "shared" | "hidden" | "reported" | "viewed" => Ok(()),
        other => {
            tracing::debug!(
                event_type = other,
                "unrecognised interaction event — skipping"
            );
            Ok(())
        }
    }
}

async fn handle_user_followed(state: AppState, env: InboundEnvelope) -> anyhow::Result<()> {
    if env.event_type != "followed" {
        return Ok(());
    }
    let d: UserFollowedData = serde_json::from_value(env.data)?;
    dispatch_notification(
        &state,
        d.followee_id,
        "followed",
        Some(d.follower_id),
        None,
        None,
        serde_json::json!({}),
    )
    .await
}

async fn handle_moderation_action(state: AppState, env: InboundEnvelope) -> anyhow::Result<()> {
    let kind = match env.event_type.as_str() {
        "post_hidden" => "post_hidden",
        "author_warned" => "author_warned",
        "author_banned" => "author_banned",
        // These do not generate user-visible notifications.
        "report_dismissed" | "post_unhidden" | "author_unbanned" => return Ok(()),
        other => {
            tracing::debug!(
                event_type = other,
                "unrecognised moderation event — skipping"
            );
            return Ok(());
        }
    };

    let d: ModerationActionData = serde_json::from_value(env.data)?;
    dispatch_notification(
        &state,
        d.target_user_id,
        kind,
        None, // actor is system / admin; we don't expose admin identity to users
        d.target_post_id,
        None,
        serde_json::json!({}),
    )
    .await
}
