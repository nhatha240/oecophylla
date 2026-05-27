use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Utc};
use uuid::Uuid;

/// Encode `(created_at, id)` as an opaque base64url cursor string.
pub fn encode(created_at: DateTime<Utc>, id: Uuid) -> String {
    let raw = format!("{}|{}", created_at.to_rfc3339(), id);
    URL_SAFE_NO_PAD.encode(raw.as_bytes())
}

/// Decode a cursor string back into `(created_at, id)`.
/// Returns `None` if the string is malformed.
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
    fn garbage_returns_none() {
        assert!(decode("not-a-cursor").is_none());
        assert!(decode("aGVsbG8").is_none());
    }
}
