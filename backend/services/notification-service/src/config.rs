#[derive(Clone, Debug)]
pub struct NotificationConfig {
    pub kafka_brokers: String,
    pub unread_cache_ttl_seconds: usize,
    pub sse_heartbeat_seconds: u64,
}

impl NotificationConfig {
    pub fn from_env() -> Self {
        Self {
            kafka_brokers: std::env::var("KAFKA_BROKERS").unwrap_or_else(|_| "kafka:9092".into()),
            unread_cache_ttl_seconds: std::env::var("NOTIF_UNREAD_CACHE_TTL_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1800),
            sse_heartbeat_seconds: std::env::var("NOTIF_SSE_HEARTBEAT_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(25),
        }
    }
}
