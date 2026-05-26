use std::time::Duration;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize)]
pub struct RecommendFeedRequest {
    pub limit: usize,
    pub candidate_pool: usize,
    pub exclude_post_ids: Vec<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct RecommendationItem {
    pub post_id: Uuid,
    pub score: f32,
    pub source: String,
    #[serde(default)]
    pub reason: String,
}

#[derive(Debug, Deserialize)]
struct RecommendFeedResponse {
    items: Vec<RecommendationItem>,
}

/// POST recommendation-api with a hard timeout. On any timeout / non-2xx /
/// decoding failure, return Err so the handler can fall back to trending.
pub async fn recommend_feed(
    client: &reqwest::Client,
    base_url: &str,
    user_id: Uuid,
    req: RecommendFeedRequest,
    timeout_ms: u64,
) -> anyhow::Result<Vec<RecommendationItem>> {
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
    Ok(parsed.items)
}
