use chrono::{DateTime, Utc};
use common::events::Envelope;
use serde::Serialize;
use uuid::Uuid;

pub const TOPIC_INTERACTIONS: &str = "oecophylla.interactions";

#[derive(Serialize)]
pub struct ToggleData {
    pub user_id: Uuid,
    pub post_id: Uuid,
    pub post_author_id: Uuid,
    pub client_event_id: Uuid,
    pub weight: f32,
}
#[derive(Serialize)]
pub struct ReportData {
    pub reporter_id: Uuid,
    pub post_id: Uuid,
    pub post_author_id: Uuid,
    pub reason: String,
    pub report_id: Uuid,
    pub client_event_id: Uuid,
}
#[derive(Serialize)]
pub struct CommentData {
    pub commenter_id: Uuid,
    pub post_id: Uuid,
    pub post_author_id: Uuid,
    pub comment_id: Uuid,
    pub parent_comment_id: Option<Uuid>,
    pub content_preview: String,
    pub client_event_id: Uuid,
}

#[derive(Serialize)]
pub struct BehaviorTelemetryData {
    pub user_id: Uuid,
    pub post_id: Uuid,
    pub client_event_id: Uuid,
    pub behavior_event_id: Uuid,
    pub impression_id: Option<Uuid>,
    pub session_id: Option<Uuid>,
    pub occurred_at: DateTime<Utc>,
}

#[derive(Serialize)]
pub struct QualifiedReadData {
    pub user_id: Uuid,
    pub post_id: Uuid,
    pub client_event_id: Uuid,
    pub behavior_event_id: Uuid,
    pub impression_id: Option<Uuid>,
    pub session_id: Option<Uuid>,
    pub occurred_at: DateTime<Utc>,
    pub duration_ms: i32,
    pub source_event_type: String,
}

/// Build the telemetry v1 envelope with a durable event identity. Reusing the
/// append-only behavior row ID makes any producer retry safe for consumers.
pub fn viewed_envelope(data: BehaviorTelemetryData) -> Envelope<BehaviorTelemetryData> {
    Envelope {
        event_id: data.behavior_event_id,
        event_type: "viewed",
        event_version: 1,
        occurred_at: data.occurred_at,
        producer: "interaction-service",
        data,
    }
}

/// Build the v2 qualified-read envelope. Its durable behavior row ID is the
/// Kafka identity, so retries are idempotent at every consumer.
pub fn qualified_read_envelope(data: QualifiedReadData) -> Envelope<QualifiedReadData> {
    Envelope {
        event_id: data.behavior_event_id,
        event_type: "qualified_read",
        event_version: 2,
        occurred_at: data.occurred_at,
        producer: "interaction-service",
        data,
    }
}

pub fn weight_for(t: &str) -> f32 {
    match t {
        "like" => env_or("INTERACTION_WEIGHT_LIKE", 1.5),
        "save" => env_or("INTERACTION_WEIGHT_SAVE", 2.5),
        "share" => env_or("INTERACTION_WEIGHT_SHARE", 2.5),
        "hide" => env_or("INTERACTION_WEIGHT_HIDE", -2.0),
        "report" => env_or("INTERACTION_WEIGHT_REPORT", -5.0),
        _ => 0.0,
    }
}
fn env_or(key: &str, default: f32) -> f32 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn viewed_envelope_matches_the_shared_v1_contract() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../tests/fixtures/recommendation_telemetry/interaction_viewed_v1.json"
        ))
        .unwrap();
        let data = BehaviorTelemetryData {
            user_id: fixture["data"]["user_id"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap(),
            post_id: fixture["data"]["post_id"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap(),
            client_event_id: fixture["data"]["client_event_id"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap(),
            behavior_event_id: fixture["data"]["behavior_event_id"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap(),
            impression_id: Some(
                fixture["data"]["impression_id"]
                    .as_str()
                    .unwrap()
                    .parse()
                    .unwrap(),
            ),
            session_id: Some(
                fixture["data"]["session_id"]
                    .as_str()
                    .unwrap()
                    .parse()
                    .unwrap(),
            ),
            occurred_at: fixture["data"]["occurred_at"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap(),
        };

        let actual = serde_json::to_value(viewed_envelope(data)).unwrap();
        assert_eq!(actual, fixture);
    }

    #[test]
    fn qualified_read_v2_uses_the_behavior_row_as_its_idempotency_key() {
        let behavior_event_id = Uuid::now_v7();
        let occurred_at = Utc::now();
        let envelope = qualified_read_envelope(QualifiedReadData {
            user_id: Uuid::now_v7(),
            post_id: Uuid::now_v7(),
            client_event_id: Uuid::now_v7(),
            behavior_event_id,
            impression_id: Some(Uuid::now_v7()),
            session_id: Some(Uuid::now_v7()),
            occurred_at,
            duration_ms: 10_000,
            source_event_type: "dwell".into(),
        });

        assert_eq!(envelope.event_id, behavior_event_id);
        assert_eq!(envelope.event_type, "qualified_read");
        assert_eq!(envelope.event_version, 2);
        assert_eq!(envelope.data.duration_ms, 10_000);
        assert_eq!(envelope.data.source_event_type, "dwell");
    }
}

pub fn counter_column(t: &str) -> Option<&'static str> {
    match t {
        "like" => Some("like_count"),
        "save" => Some("save_count"),
        "share" => Some("share_count"),
        _ => None,
    }
}
