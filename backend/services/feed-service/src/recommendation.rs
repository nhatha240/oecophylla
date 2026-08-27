use std::time::Duration;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize)]
pub struct RecommendFeedRequest {
    pub limit: usize,
    pub candidate_pool: usize,
    pub exclude_post_ids: Vec<Uuid>,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum RankFeatureSchemaVersion {
    #[serde(rename = "rank-features-v1")]
    V1,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RankFeatureSnapshot {
    pub schema_version: RankFeatureSchemaVersion,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub topic_relevance: Option<f64>,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub freshness: Option<f64>,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub safety_score: Option<f64>,
    pub candidate_source: String,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub is_followed_author: Option<bool>,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub author_affinity: Option<f64>,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub heuristic_score: Option<f64>,
    #[serde(deserialize_with = "deserialize_required_nullable")]
    pub ml_score: Option<f64>,
}

impl RankFeatureSnapshot {
    pub fn unranked(candidate_source: impl Into<String>) -> Self {
        Self {
            schema_version: RankFeatureSchemaVersion::V1,
            topic_relevance: None,
            freshness: None,
            safety_score: None,
            candidate_source: candidate_source.into(),
            is_followed_author: None,
            author_affinity: None,
            heuristic_score: None,
            ml_score: None,
        }
    }
}

fn deserialize_required_nullable<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(deserializer)
}

#[derive(Debug, Deserialize)]
pub struct RecommendationItem {
    pub post_id: Uuid,
    pub score: f32,
    pub source: String,
    #[serde(default)]
    pub reason: String,
    pub features: RankFeatureSnapshot,
}

#[derive(Debug, Deserialize)]
pub struct RecommendFeedResponse {
    pub items: Vec<RecommendationItem>,
    pub model_version: String,
}

/// POST recommendation-api with a hard timeout. On any timeout / non-2xx /
/// decoding failure, return Err so the handler can fall back to trending.
pub async fn recommend_feed(
    client: &reqwest::Client,
    base_url: &str,
    user_id: Uuid,
    req: RecommendFeedRequest,
    timeout_ms: u64,
) -> anyhow::Result<RecommendFeedResponse> {
    let url = format!("{base_url}/recommend/feed/{user_id}");
    let res = tokio::time::timeout(
        Duration::from_millis(timeout_ms),
        client.post(url).json(&req).send(),
    )
    .await
    .map_err(|_| anyhow::anyhow!("recommendation-api request timed out"))??;
    if !res.status().is_success() {
        anyhow::bail!("recommendation-api returned {}", res.status());
    }
    let parsed: RecommendFeedResponse = res.json().await?;
    Ok(parsed)
}

#[cfg(test)]
mod recommendation_contract_tests {
    use super::*;

    const VALID_RESPONSE: &str = r#"{
        "items": [{
            "post_id": "00000000-0000-0000-0000-000000000001",
            "score": 0.79,
            "source": "topic",
            "reason": "heuristic-rank",
            "features": {
                "schema_version": "rank-features-v1",
                "topic_relevance": 0.8,
                "freshness": 0.7,
                "safety_score": 0.9,
                "candidate_source": "topic",
                "is_followed_author": null,
                "author_affinity": null,
                "heuristic_score": 0.79,
                "ml_score": null
            }
        }],
        "model_version": "heuristic-v1",
        "generated_at": "2026-08-27T00:00:00Z"
    }"#;

    #[test]
    fn recommendation_contract_decodes_versioned_feature_snapshot() {
        let response: RecommendFeedResponse = serde_json::from_str(VALID_RESPONSE).unwrap();

        assert_eq!(response.model_version, "heuristic-v1");
        assert_eq!(response.items.len(), 1);
        let features = &response.items[0].features;
        assert!(matches!(
            features.schema_version,
            RankFeatureSchemaVersion::V1
        ));
        assert_eq!(features.candidate_source, "topic");
        assert_eq!(features.topic_relevance, Some(0.8));
        assert_eq!(features.freshness, Some(0.7));
        assert_eq!(features.safety_score, Some(0.9));
        assert_eq!(features.author_affinity, None);
        assert_eq!(features.heuristic_score, Some(0.79));
        assert_eq!(features.ml_score, None);
        assert_eq!(features.is_followed_author, None);

        let encoded = serde_json::to_value(features).unwrap();
        assert_eq!(encoded["schema_version"], "rank-features-v1");
        assert_eq!(encoded["author_affinity"], serde_json::Value::Null);
        assert_eq!(encoded["ml_score"], serde_json::Value::Null);
    }

    #[test]
    fn recommendation_contract_rejects_missing_feature_schema_version() {
        let payload = VALID_RESPONSE.replace("\"schema_version\": \"rank-features-v1\",", "");

        assert!(serde_json::from_str::<RecommendFeedResponse>(&payload).is_err());
    }

    #[test]
    fn recommendation_contract_rejects_unsupported_feature_schema_version() {
        let payload = VALID_RESPONSE.replace("rank-features-v1", "rank-features-v2");

        assert!(serde_json::from_str::<RecommendFeedResponse>(&payload).is_err());
    }

    #[test]
    fn recommendation_contract_requires_nullable_fields_to_be_explicit() {
        let mut payload: serde_json::Value = serde_json::from_str(VALID_RESPONSE).unwrap();
        payload["items"][0]["features"]
            .as_object_mut()
            .unwrap()
            .remove("ml_score");

        assert!(serde_json::from_value::<RecommendFeedResponse>(payload).is_err());
    }

    #[test]
    fn recommendation_contract_rejects_missing_model_version() {
        let payload = VALID_RESPONSE.replace("\"model_version\": \"heuristic-v1\",", "");

        assert!(serde_json::from_str::<RecommendFeedResponse>(&payload).is_err());
    }
}
