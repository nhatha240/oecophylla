use chrono::{DateTime, Utc};
use common::events::Envelope;
use serde::Serialize;
use serde_json::Value;
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

/// Build the v2 qualified-read envelope. Recommendation-attributed reads use
/// the impression as their semantic identity, collapsing a threshold `view`
/// and later `dwell` into one feature delta. Direct-entry reads fall back to
/// the durable behavior row ID.
pub fn qualified_read_envelope(data: QualifiedReadData) -> Envelope<QualifiedReadData> {
    Envelope {
        event_id: data.impression_id.unwrap_or(data.behavior_event_id),
        event_type: "qualified_read",
        event_version: 2,
        occurred_at: data.occurred_at,
        producer: "interaction-service",
        data,
    }
}

pub fn feature_event_envelope(
    feature_event_version: &str,
    data: QualifiedReadData,
) -> Option<Value> {
    if feature_event_version == crate::label_contract::LABEL_V2 {
        return serde_json::to_value(qualified_read_envelope(data)).ok();
    }
    if feature_event_version != crate::label_contract::LABEL_V1 || data.source_event_type != "view"
    {
        return None;
    }
    serde_json::to_value(viewed_envelope(BehaviorTelemetryData {
        user_id: data.user_id,
        post_id: data.post_id,
        client_event_id: data.client_event_id,
        behavior_event_id: data.behavior_event_id,
        impression_id: data.impression_id,
        session_id: data.session_id,
        occurred_at: data.occurred_at,
    }))
    .ok()
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
    fn qualified_read_v2_deduplicates_view_and_dwell_for_one_impression() {
        let impression_id = Uuid::now_v7();
        let occurred_at = Utc::now();
        let view = qualified_read_envelope(QualifiedReadData {
            user_id: Uuid::now_v7(),
            post_id: Uuid::now_v7(),
            client_event_id: Uuid::now_v7(),
            behavior_event_id: Uuid::now_v7(),
            impression_id: Some(impression_id),
            session_id: Some(Uuid::now_v7()),
            occurred_at,
            duration_ms: 10_000,
            source_event_type: "view".into(),
        });
        let dwell = qualified_read_envelope(QualifiedReadData {
            user_id: view.data.user_id,
            post_id: view.data.post_id,
            client_event_id: Uuid::now_v7(),
            behavior_event_id: Uuid::now_v7(),
            impression_id: Some(impression_id),
            session_id: view.data.session_id,
            occurred_at,
            duration_ms: 12_000,
            source_event_type: "dwell".into(),
        });

        assert_eq!(view.event_id, impression_id);
        assert_eq!(dwell.event_id, impression_id);
        assert_eq!(view.event_type, "qualified_read");
        assert_eq!(view.event_version, 2);
    }

    #[test]
    fn direct_entry_qualified_read_uses_the_durable_behavior_id() {
        let behavior_event_id = Uuid::now_v7();
        let envelope = qualified_read_envelope(QualifiedReadData {
            user_id: Uuid::now_v7(),
            post_id: Uuid::now_v7(),
            client_event_id: Uuid::now_v7(),
            behavior_event_id,
            impression_id: None,
            session_id: Some(Uuid::now_v7()),
            occurred_at: Utc::now(),
            duration_ms: 10_000,
            source_event_type: "dwell".into(),
        });
        assert_eq!(envelope.event_id, behavior_event_id);
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
