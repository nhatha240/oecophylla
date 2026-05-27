use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Utc};
use uuid::Uuid;

/// Opaque cursor: base64url(`<rfc3339_created_at>|<uuid>`).
///
/// Pagination uses the `(created_at, id) < (cursor_created_at, cursor_id)` predicate
/// so the partial pending index on `reports(created_at DESC) WHERE status='pending'`
/// is hit, and so the secondary tie-break on id makes the ordering total.
pub fn encode(created_at: DateTime<Utc>, id: Uuid) -> String {
    let raw = format!("{}|{}", created_at.to_rfc3339(), id);
    URL_SAFE_NO_PAD.encode(raw.as_bytes())
}

pub fn decode(s: &str) -> Option<(DateTime<Utc>, Uuid)> {
    let bytes = URL_SAFE_NO_PAD.decode(s.as_bytes()).ok()?;
    let raw = std::str::from_utf8(&bytes).ok()?;
    let mut parts = raw.splitn(2, '|');
    let ts = parts.next()?;
    let id = parts.next()?;
    let created_at = DateTime::parse_from_rfc3339(ts).ok()?.with_timezone(&Utc);
    let uuid = Uuid::parse_str(id).ok()?;
    Some((created_at, uuid))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip() {
        let now = Utc::now();
        let id = Uuid::now_v7();
        let encoded = encode(now, id);
        let (ts, uid) = decode(&encoded).expect("decoded");
        assert_eq!(uid, id);
        assert_eq!(ts.timestamp_millis(), now.timestamp_millis());
    }

    #[test]
    fn decode_garbage_returns_none() {
        assert!(decode("not-a-cursor").is_none());
        assert!(decode("aGVsbG8").is_none());
    }
}
