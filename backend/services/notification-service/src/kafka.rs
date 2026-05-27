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
