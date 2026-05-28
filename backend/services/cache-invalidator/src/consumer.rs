use anyhow::Context;
use deadpool_redis::Pool as RedisPool;
use rdkafka::{
    config::ClientConfig,
    consumer::{Consumer, StreamConsumer},
    Message,
};
use deadpool_redis::redis::AsyncCommands;
use serde::Deserialize;

const TOPIC: &str = "oecophylla.interactions";
const GROUP_ID: &str = "oecophylla.feed.cache-invalidator.v1";

#[derive(Debug, Deserialize)]
struct Envelope {
    #[serde(default)]
    event_type: Option<String>,
    #[serde(default)]
    data: serde_json::Value,
}

pub fn build_consumer(brokers: &str) -> anyhow::Result<StreamConsumer> {
    Ok(ClientConfig::new()
        .set("bootstrap.servers", brokers)
        .set("group.id", GROUP_ID)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest")
        .create()?)
}

pub async fn run(brokers: String, redis: RedisPool) -> anyhow::Result<()> {
    let consumer = build_consumer(&brokers).context("build kafka consumer")?;
    consumer.subscribe(&[TOPIC])?;
    tracing::info!(%TOPIC, group = GROUP_ID, "cache-invalidator subscribed");

    loop {
        let msg = match consumer.recv().await {
            Ok(m) => m,
            Err(err) => {
                tracing::warn!(error = %err, "kafka recv error");
                continue;
            }
        };

        let payload = match msg.payload() {
            Some(p) => p,
            None => continue,
        };
        let env: Envelope = match serde_json::from_slice(payload) {
            Ok(e) => e,
            Err(err) => {
                tracing::warn!(error = %err, "skipping malformed envelope");
                let _ = consumer.commit_message(&msg, rdkafka::consumer::CommitMode::Async);
                continue;
            }
        };

        if let Some(user_id) = extract_user_id(&env) {
            let key = format!("feed:{user_id}");
            match redis.get().await {
                Ok(mut conn) => match conn.del::<_, i64>(&key).await {
                    Ok(deleted) => tracing::debug!(%user_id, %deleted, "feed cache invalidated"),
                    Err(err) => tracing::warn!(error = %err, %user_id, "redis DEL failed"),
                },
                Err(err) => tracing::warn!(error = %err, "redis pool acquire failed"),
            }
        }

        if let Err(err) = consumer.commit_message(&msg, rdkafka::consumer::CommitMode::Async) {
            tracing::warn!(error = %err, "kafka commit failed");
        }
    }
}

fn extract_user_id(env: &Envelope) -> Option<String> {
    let data = env.data.as_object()?;
    for key in ["user_id", "reporter_id", "commenter_id"] {
        if let Some(v) = data.get(key).and_then(|v| v.as_str()) {
            return Some(v.to_string());
        }
    }
    let _ = &env.event_type;
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_user_id_first() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"liked","data":{"user_id":"abc","post_id":"xyz"}}"#,
        )
        .unwrap();
        assert_eq!(extract_user_id(&env).as_deref(), Some("abc"));
    }

    #[test]
    fn falls_back_to_reporter_id() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"reported","data":{"reporter_id":"r1","post_id":"xyz"}}"#,
        )
        .unwrap();
        assert_eq!(extract_user_id(&env).as_deref(), Some("r1"));
    }

    #[test]
    fn returns_none_when_no_user_field() {
        let env: Envelope =
            serde_json::from_str(r#"{"event_type":"orphan","data":{"post_id":"xyz"}}"#).unwrap();
        assert!(extract_user_id(&env).is_none());
    }

    #[test]
    fn extracts_commenter_id_as_third_priority() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"commented","data":{"commenter_id":"c1","post_id":"xyz"}}"#,
        )
        .unwrap();
        assert_eq!(extract_user_id(&env).as_deref(), Some("c1"));
    }

    #[test]
    fn user_id_takes_priority_over_reporter_and_commenter() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"mixed","data":{"user_id":"u1","reporter_id":"r1","commenter_id":"c1"}}"#,
        )
        .unwrap();
        assert_eq!(extract_user_id(&env).as_deref(), Some("u1"));
    }

    #[test]
    fn reporter_id_takes_priority_over_commenter() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"mixed","data":{"reporter_id":"r1","commenter_id":"c1"}}"#,
        )
        .unwrap();
        assert_eq!(extract_user_id(&env).as_deref(), Some("r1"));
    }

    #[test]
    fn non_string_user_id_is_skipped() {
        let env: Envelope = serde_json::from_str(
            r#"{"event_type":"bad","data":{"user_id":12345,"reporter_id":"r1"}}"#,
        )
        .unwrap();
        // user_id is a number, not a string → should fall through to reporter_id.
        assert_eq!(extract_user_id(&env).as_deref(), Some("r1"));
    }

    #[test]
    fn empty_data_object_returns_none() {
        let env: Envelope =
            serde_json::from_str(r#"{"event_type":"empty","data":{}}"#).unwrap();
        assert!(extract_user_id(&env).is_none());
    }

    #[test]
    fn non_object_data_returns_none() {
        let env: Envelope =
            serde_json::from_str(r#"{"event_type":"array","data":[1,2,3]}"#).unwrap();
        assert!(extract_user_id(&env).is_none());
    }

    #[test]
    fn envelope_with_missing_event_type_defaults_to_none() {
        let env: Envelope =
            serde_json::from_str(r#"{"data":{"user_id":"u1"}}"#).unwrap();
        assert!(env.event_type.is_none());
    }

    #[test]
    fn envelope_with_null_data_returns_none() {
        let env: Envelope =
            serde_json::from_str(r#"{"event_type":"test","data":null}"#).unwrap();
        assert!(extract_user_id(&env).is_none());
    }
}
