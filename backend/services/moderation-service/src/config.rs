use common::events::TOPIC_MODERATION_ACTION;

#[derive(Clone, Debug)]
pub struct ModerationConfig {
    pub kafka_brokers: String,
    pub moderation_topic: String,
}

impl ModerationConfig {
    pub fn from_env() -> Self {
        Self {
            kafka_brokers: std::env::var("KAFKA_BROKERS")
                .unwrap_or_else(|_| "kafka:9092".into()),
            moderation_topic: std::env::var("MODERATION_TOPIC")
                .unwrap_or_else(|_| TOPIC_MODERATION_ACTION.into()),
        }
    }
}
