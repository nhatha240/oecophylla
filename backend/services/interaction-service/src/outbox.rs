use common::kafka::Producer;
use serde_json::Value;
use sqlx::{types::Json, PgPool};
use std::time::Duration;
use uuid::Uuid;

const BATCH_SIZE: usize = 32;
const IDLE_POLL_INTERVAL: Duration = Duration::from_millis(500);
const FAILURE_POLL_INTERVAL: Duration = Duration::from_secs(1);
const DB_ERROR_INTERVAL: Duration = Duration::from_secs(2);
const CLEANUP_BATCH_SIZE: i64 = 500;
const CLEANUP_BACKLOG_INTERVAL: Duration = Duration::from_millis(100);
const CLEANUP_IDLE_INTERVAL: Duration = Duration::from_secs(60 * 60);
const CLEANUP_ERROR_INTERVAL: Duration = Duration::from_secs(60);

#[derive(sqlx::FromRow)]
struct PendingEvent {
    event_id: Uuid,
    topic: String,
    partition_key: String,
    payload: Json<Value>,
}

struct DispatchResult {
    event_id: Uuid,
    failed: bool,
}

struct BatchResult {
    processed: usize,
    failed: usize,
}

pub async fn run(db: PgPool, kafka: Producer) {
    tokio::spawn(clean_sent_events(db.clone()));
    loop {
        match dispatch_batch(&db, &kafka).await {
            Ok(batch) if batch.failed > 0 => {
                tokio::time::sleep(FAILURE_POLL_INTERVAL).await;
            }
            Ok(batch) if batch.processed < BATCH_SIZE => {
                tokio::time::sleep(IDLE_POLL_INTERVAL).await;
            }
            Ok(_) => tokio::task::yield_now().await,
            Err(error) => {
                tracing::error!(?error, "interaction outbox dispatch failed");
                tokio::time::sleep(DB_ERROR_INTERVAL).await;
            }
        }
    }
}

async fn clean_sent_events(db: PgPool) {
    loop {
        let delay = match cleanup_batch(&db).await {
            Ok(deleted) if deleted >= CLEANUP_BATCH_SIZE => CLEANUP_BACKLOG_INTERVAL,
            Ok(_) => CLEANUP_IDLE_INTERVAL,
            Err(error) => {
                tracing::error!(?error, "interaction outbox cleanup failed");
                CLEANUP_ERROR_INTERVAL
            }
        };
        tokio::time::sleep(delay).await;
    }
}

async fn cleanup_batch(db: &PgPool) -> anyhow::Result<i64> {
    let result = sqlx::query(
        r#"
        WITH expired AS (
            SELECT event_id
            FROM interaction_event_outbox
            WHERE sent_at < NOW() - INTERVAL '7 days'
            ORDER BY sent_at, event_id
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM interaction_event_outbox AS outbox
        USING expired
        WHERE outbox.event_id = expired.event_id
        "#,
    )
    .bind(CLEANUP_BATCH_SIZE)
    .execute(db)
    .await?;
    Ok(result.rows_affected() as i64)
}

async fn dispatch_batch(db: &PgPool, kafka: &Producer) -> anyhow::Result<BatchResult> {
    // A failed row is skipped for the rest of this batch so it cannot starve
    // later events when Kafka rejects it quickly.
    let mut attempted = Vec::with_capacity(BATCH_SIZE);
    let mut failed = 0;
    while attempted.len() < BATCH_SIZE {
        let Some(result) = dispatch_next(db, kafka, &attempted).await? else {
            break;
        };
        attempted.push(result.event_id);
        failed += usize::from(result.failed);
    }
    Ok(BatchResult {
        processed: attempted.len(),
        failed,
    })
}

async fn dispatch_next(
    db: &PgPool,
    kafka: &Producer,
    attempted: &[Uuid],
) -> anyhow::Result<Option<DispatchResult>> {
    let mut tx = db.begin().await?;
    let event = sqlx::query_as::<_, PendingEvent>(
        r#"
        SELECT event_id, topic, partition_key, payload
        FROM interaction_event_outbox
        WHERE sent_at IS NULL
          AND event_id <> ALL($1::uuid[])
        ORDER BY created_at, event_id
        LIMIT 1
        FOR UPDATE SKIP LOCKED
        "#,
    )
    .bind(attempted)
    .fetch_optional(&mut *tx)
    .await?;
    let Some(event) = event else {
        tx.commit().await?;
        return Ok(None);
    };

    // Keep the row locked until Kafka acknowledges delivery and its receipt is
    // recorded. A crash between those operations may resend the same event_id;
    // consumers must use the envelope identity to deduplicate it.
    let send_result = kafka
        .try_produce_json(&event.topic, &event.partition_key, &event.payload.0)
        .await;
    let failed = match send_result {
        Ok(()) => {
            sqlx::query(
                r#"
                UPDATE interaction_event_outbox
                SET sent_at = NOW(), attempts = attempts + 1, last_error = NULL
                WHERE event_id = $1
                "#,
            )
            .bind(event.event_id)
            .execute(&mut *tx)
            .await?;
            false
        }
        Err(error) => {
            let message: String = error.to_string().chars().take(2000).collect();
            sqlx::query(
                r#"
                UPDATE interaction_event_outbox
                SET attempts = attempts + 1, last_error = $2
                WHERE event_id = $1
                "#,
            )
            .bind(event.event_id)
            .bind(message)
            .execute(&mut *tx)
            .await?;
            tracing::warn!(event_id = %event.event_id, ?error, "interaction outbox publish failed");
            true
        }
    };
    tx.commit().await?;
    Ok(Some(DispatchResult {
        event_id: event.event_id,
        failed,
    }))
}
