use serde_json::{Map, Value};
use std::collections::{HashMap, HashSet};

pub const QUALIFIED_READ_MS: i32 = 10_000;
pub const LABEL_V1: &str = "v1";
pub const LABEL_V2: &str = "v2";

#[derive(Debug)]
pub struct LabelResult {
    pub semantic: String,
    pub training_target: Option<i64>,
    pub accepted_events: usize,
    pub deduplicated_events: usize,
    pub processing_order: Vec<String>,
}

fn canonicalize(value: &Value) -> Value {
    match value {
        Value::Array(items) => Value::Array(items.iter().map(canonicalize).collect()),
        Value::Object(items) => {
            let mut keys = items.keys().collect::<Vec<_>>();
            keys.sort();
            let mut canonical = Map::new();
            for key in keys {
                canonical.insert(key.clone(), canonicalize(&items[key]));
            }
            Value::Object(canonical)
        }
        _ => value.clone(),
    }
}

fn canonical_payload(event: &Map<String, Value>) -> Result<String, String> {
    serde_json::to_string(&canonicalize(&Value::Object(event.clone())))
        .map_err(|error| error.to_string())
}

fn duration(event: &Map<String, Value>) -> Option<i64> {
    event
        .get("continuous_visible_ms")
        .and_then(Value::as_i64)
        .or_else(|| event.get("dwell_ms").and_then(Value::as_i64))
        .or_else(|| {
            event
                .get("metadata")
                .and_then(Value::as_object)
                .and_then(|metadata| metadata.get("continuous_visible_ms"))
                .and_then(Value::as_i64)
        })
}

pub fn derive_label_v2(
    events: &[Value],
    defaults: &Map<String, Value>,
    qualified_read_ms: i64,
    label_window_closed: bool,
) -> Result<LabelResult, String> {
    if qualified_read_ms <= 0 {
        return Err("qualified_read_ms must be positive".into());
    }
    let mut unique: HashMap<String, Map<String, Value>> = HashMap::new();
    let mut anonymous = Vec::new();
    let mut deduplicated_events = 0;
    for raw in events {
        let raw = raw
            .as_object()
            .ok_or_else(|| "event must be an object".to_string())?;
        let mut event = defaults.clone();
        event.extend(raw.clone());
        match event.get("event_id").and_then(Value::as_str) {
            Some(event_id) => match unique.get(event_id) {
                Some(existing) if canonical_payload(existing)? != canonical_payload(&event)? => {
                    return Err(format!("conflicting duplicate event: {event_id}"));
                }
                Some(_) => deduplicated_events += 1,
                None => {
                    unique.insert(event_id.to_string(), event);
                }
            },
            None => anonymous.push(event),
        }
    }
    let mut accepted = unique.into_values().chain(anonymous).collect::<Vec<_>>();
    accepted.sort_by_key(|event| {
        (
            event
                .get("occurred_at")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            event
                .get("ingested_at")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            event
                .get("event_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
        )
    });
    let accepted_events = accepted.len();
    let processing_order = accepted
        .iter()
        .map(|event| {
            event
                .get("event_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string()
        })
        .collect();

    let mut active = HashMap::from([
        ("like", false),
        ("save", false),
        ("share", false),
        ("hide", false),
    ]);
    let reversals = HashMap::from([
        ("unlike", "like"),
        ("unsave", "save"),
        ("unshare", "share"),
        ("unhide", "hide"),
    ]);
    let mut candidates: HashSet<&str> = HashSet::new();
    let mut visible = false;
    for event in accepted {
        let event_type = event
            .get("event_type")
            .and_then(Value::as_str)
            .unwrap_or("");
        if let Some(value) = active.get_mut(event_type) {
            *value = true;
        } else if let Some(reversed) = reversals.get(event_type) {
            active.insert(reversed, false);
        } else {
            match event_type {
                "visible" => visible = true,
                "click" => {
                    candidates.insert("click");
                }
                "comment" => {
                    candidates.insert("positive");
                }
                "report" => {
                    candidates.insert("strong_negative");
                }
                _ => {}
            }
        }
        if matches!(event_type, "view" | "dwell")
            && duration(&event).is_some_and(|value| value >= qualified_read_ms)
        {
            candidates.insert("qualified_read");
        }
    }
    if active["hide"] {
        candidates.insert("strong_negative");
    }
    if active["save"] || active["share"] {
        candidates.insert("strong_positive");
    }
    if active["like"] {
        candidates.insert("positive");
    }
    if visible {
        candidates.insert(if label_window_closed {
            "negative"
        } else {
            "exposure"
        });
    }
    if candidates.is_empty() {
        candidates.insert(if label_window_closed {
            "negative"
        } else {
            "exposure"
        });
    }
    let semantic = [
        "strong_negative",
        "strong_positive",
        "positive",
        "qualified_read",
        "click",
        "negative",
        "exposure",
    ]
    .into_iter()
    .find(|semantic| candidates.contains(semantic))
    .expect("at least one semantic")
    .to_string();
    let training_target = match semantic.as_str() {
        "exposure" => None,
        "click" | "qualified_read" | "positive" | "strong_positive" => Some(1),
        _ => Some(0),
    };
    Ok(LabelResult {
        semantic,
        training_target,
        accepted_events,
        deduplicated_events,
        processing_order,
    })
}
