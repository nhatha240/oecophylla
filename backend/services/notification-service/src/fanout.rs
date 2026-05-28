use std::{collections::HashMap, sync::Mutex};

use tokio::sync::broadcast;
use uuid::Uuid;

use crate::types::NotificationDto;

const CHANNEL_CAPACITY: usize = 64;

/// In-process fan-out registry: maps `user_id → list of broadcast senders`.
///
/// Multiple SSE connections for the same user each get their own `Receiver`;
/// they all share the same `Sender`.  When a connection drops, its dead sender
/// is pruned on the next `publish` call.
pub struct Fanout {
    map: Mutex<HashMap<Uuid, Vec<broadcast::Sender<NotificationDto>>>>,
}

impl Fanout {
    pub fn new() -> Self {
        Self {
            map: Mutex::new(HashMap::new()),
        }
    }

    /// Subscribe to real-time notifications for `user_id`.
    /// Each call creates a fresh broadcast channel (and therefore a fresh
    /// `Receiver`) so that concurrent SSE connections don't starve each other.
    pub fn subscribe(&self, user_id: Uuid) -> broadcast::Receiver<NotificationDto> {
        let (tx, rx) = broadcast::channel(CHANNEL_CAPACITY);
        let mut guard = self.map.lock().expect("fanout lock poisoned");
        guard.entry(user_id).or_default().push(tx);
        rx
    }

    /// Publish `dto` to all live SSE connections for `user_id`.
    /// Dead senders (where all receivers have been dropped) are pruned in place.
    pub fn publish(&self, user_id: Uuid, dto: NotificationDto) {
        let mut guard = self.map.lock().expect("fanout lock poisoned");
        if let Some(senders) = guard.get_mut(&user_id) {
            senders.retain(|tx| {
                // `send` returns `Err` when there are no receivers left.
                tx.send(dto.clone()).is_ok()
            });
            if senders.is_empty() {
                guard.remove(&user_id);
            }
        }
    }
}

impl Default for Fanout {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn sample_dto() -> NotificationDto {
        NotificationDto {
            id: Uuid::parse_str("00000000-0000-0000-0000-000000000001").unwrap(),
            kind: "liked".into(),
            actor: None,
            post: None,
            comment_id: None,
            payload: serde_json::json!({}),
            read: false,
            created_at: Utc::now(),
        }
    }

    #[test]
    fn new_fanout_is_empty() {
        let f = Fanout::new();
        let guard = f.map.lock().unwrap();
        assert!(guard.is_empty());
    }

    #[tokio::test]
    async fn subscribe_creates_receiver() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        let _rx = f.subscribe(user_id);
        let guard = f.map.lock().unwrap();
        assert!(guard.contains_key(&user_id));
        assert_eq!(guard[&user_id].len(), 1);
    }

    #[tokio::test]
    async fn publish_reaches_subscriber() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        let mut rx = f.subscribe(user_id);
        let dto = sample_dto();

        f.publish(user_id, dto.clone());

        let received = rx.recv().await.unwrap();
        assert_eq!(received.id, dto.id);
        assert_eq!(received.kind, dto.kind);
    }

    #[tokio::test]
    async fn multiple_subscribers_all_receive() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        let mut rx1 = f.subscribe(user_id);
        let mut rx2 = f.subscribe(user_id);

        f.publish(user_id, sample_dto());

        assert!(rx1.recv().await.is_ok());
        assert!(rx2.recv().await.is_ok());
    }

    #[tokio::test]
    async fn publish_to_unknown_user_does_not_panic() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        f.publish(user_id, sample_dto()); // no subscriber — should be a no-op
    }

    #[tokio::test]
    async fn dead_sender_is_pruned() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        let rx = f.subscribe(user_id);

        // Drop the receiver — sender becomes dead.
        drop(rx);

        f.publish(user_id, sample_dto());

        let guard = f.map.lock().unwrap();
        assert!(
            !guard.contains_key(&user_id),
            "dead sender should have been pruned and entry removed"
        );
    }

    #[tokio::test]
    async fn mixed_live_and_dead_senders() {
        let f = Fanout::new();
        let user_id = Uuid::new_v4();
        let mut rx_live = f.subscribe(user_id);
        let rx_dead = f.subscribe(user_id);

        // Drop one receiver.
        drop(rx_dead);

        f.publish(user_id, sample_dto());

        // Live receiver should still get the message.
        assert!(rx_live.recv().await.is_ok());

        // The dead sender should be pruned; only the live one remains.
        let guard = f.map.lock().unwrap();
        assert_eq!(guard[&user_id].len(), 1);
    }

    #[tokio::test]
    async fn different_users_are_isolated() {
        let f = Fanout::new();
        let user_a = Uuid::new_v4();
        let user_b = Uuid::new_v4();
        let mut rx_a = f.subscribe(user_a);
        let mut rx_b = f.subscribe(user_b);

        f.publish(user_a, sample_dto());

        // user_a receives, user_b does not.
        assert!(rx_a.recv().await.is_ok());
        assert!(rx_b.try_recv().is_err());
    }
}
