use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Utc};
use uuid::Uuid;

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
