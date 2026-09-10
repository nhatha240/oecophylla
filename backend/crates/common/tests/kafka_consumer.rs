use common::{events::InboundEnvelope, kafka::decode_envelope};

#[test]
fn shared_inbound_envelope_preserves_type_and_data() {
    let envelope: InboundEnvelope = decode_envelope(
        br#"{"event_type":"liked","data":{"user_id":"user-1"}}"#,
    )
    .expect("valid event envelope");

    assert_eq!(envelope.event_type, "liked");
    assert_eq!(envelope.data["user_id"], "user-1");
}

#[test]
fn shared_inbound_envelope_rejects_missing_data() {
    let result: serde_json::Result<InboundEnvelope> =
        decode_envelope(br#"{"event_type":"liked"}"#);

    assert!(result.is_err());
}
