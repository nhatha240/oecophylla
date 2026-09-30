use rdkafka::{
    producer::{FutureProducer, FutureRecord},
    ClientConfig,
};
use serde::Serialize;
use std::time::Duration;

#[derive(Clone)]
pub struct Producer {
    inner: FutureProducer,
}

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

    pub async fn try_produce_json<T: Serialize>(
        &self,
        topic: &str,
        key: &str,
        payload: &T,
    ) -> anyhow::Result<()> {
        let body = serde_json::to_vec(payload)?;
        let rec = FutureRecord::to(topic).key(key).payload(&body);
        self.inner
            .send(rec, Duration::from_secs(5))
            .await
            .map_err(|(error, _)| anyhow::Error::new(error))?;
        Ok(())
    }

    pub async fn produce_json<T: Serialize>(&self, topic: &str, key: &str, payload: &T) {
        if let Err(error) = self.try_produce_json(topic, key, payload).await {
            tracing::error!(?error, topic, key, "kafka produce failed");
        }
    }
}
