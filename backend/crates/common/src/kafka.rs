use rdkafka::{producer::{FutureProducer, FutureRecord}, ClientConfig};
use serde::Serialize;
use std::time::Duration;

#[derive(Clone)]
pub struct Producer { inner: FutureProducer }

impl Producer {
    pub fn new(brokers: &str) -> anyhow::Result<Self> {
        let inner: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", brokers)
            .set("enable.idempotence", "true")
            .set("acks", "all")
            .set("compression.type", "lz4")
            .set("message.timeout.ms", "10000")
            .create()?;
        Ok(Self { inner })
    }

    pub async fn produce_json<T: Serialize>(&self, topic: &str, key: &str, payload: &T) {
        let body = match serde_json::to_vec(payload) {
            Ok(b) => b,
            Err(e) => { tracing::error!(error=?e, topic, "serialize event"); return; }
        };
        let rec = FutureRecord::to(topic).key(key).payload(&body);
        if let Err((e, _)) = self.inner.send(rec, Duration::from_secs(5)).await {
            tracing::error!(error=?e, topic, key, "kafka produce failed");
        }
    }
}
