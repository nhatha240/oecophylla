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
