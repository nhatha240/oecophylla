use std::{collections::HashMap, sync::Mutex};

use tokio::sync::broadcast;
use uuid::Uuid;

use crate::comment_dto::CommentDto;

const CHANNEL_CAPACITY: usize = 64;

/// In-process fan-out registry: maps `post_id → list of broadcast senders`.
///
/// Multiple SSE connections for the same post each get their own `Receiver`;
/// they all share the same `Sender`.  When a connection drops, its dead sender
/// is pruned on the next `publish` call.
pub struct CommentFanout {
    map: Mutex<HashMap<Uuid, Vec<broadcast::Sender<CommentDto>>>>,
}

impl CommentFanout {
    pub fn new() -> Self {
        Self {
            map: Mutex::new(HashMap::new()),
        }
    }

    /// Subscribe to real-time comments for `post_id`.
    /// Each call creates a fresh broadcast channel (and therefore a fresh
    /// `Receiver`) so that concurrent SSE connections don't starve each other.
    pub fn subscribe(&self, post_id: Uuid) -> broadcast::Receiver<CommentDto> {
        let (tx, rx) = broadcast::channel(CHANNEL_CAPACITY);
        let mut guard = self.map.lock().expect("comment fanout lock poisoned");
        guard.entry(post_id).or_default().push(tx);
        rx
    }

    /// Publish `dto` to all live SSE connections for `post_id`.
    /// Dead senders (where all receivers have been dropped) are pruned in place.
    pub fn publish(&self, post_id: Uuid, dto: CommentDto) {
        let mut guard = self.map.lock().expect("comment fanout lock poisoned");
        if let Some(senders) = guard.get_mut(&post_id) {
            senders.retain(|tx| {
                // `send` returns `Err` when there are no receivers left.
                tx.send(dto.clone()).is_ok()
            });
            if senders.is_empty() {
                guard.remove(&post_id);
            }
        }
    }
}

impl Default for CommentFanout {
    fn default() -> Self {
        Self::new()
    }
}
