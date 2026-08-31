# Recommendation engagement label contract v2

**Contract version:** `engagement-label-v2`

**Machine-readable source:** `docs/contracts/recommendation-label-v2.json`

**Shared conformance cases:** `tests/fixtures/recommendation_telemetry/label-v2-cases.json`

## 1. Phạm vi và nguyên tắc chuẩn tắc

Contract này là nguồn chân lý chung cho telemetry, feature event, dataset builder và evaluator. Các từ “phải”, “không được” và “từ chối” trong tài liệu là yêu cầu bắt buộc. File JSON là đầu vào máy đọc được; tài liệu này giải thích cách áp dụng mà không tạo thêm một bộ quy tắc riêng.

V2 giữ dữ liệu v1 có thể đọc để audit và rollback. Một training/evaluation run chỉ được dùng đúng một label version: dữ liệu `v1` và `v2` **không được trộn** trong cùng run, artifact hoặc báo cáo so sánh.

## 2. Rollout

Ba cấu hình bắt buộc:

| Biến | Giá trị | Mặc định | Vai trò |
|---|---|---|---|
| `RECOMMENDATION_LABEL_VERSION` | `v1`, `v2` | `v1` | Chọn logic tạo label cho dataset/evaluation |
| `FEATURE_EVENT_VERSION` | `v1`, `v2` | `v1` | Chọn producer/consumer của feature event |
| `QUALIFIED_READ_MS` | số nguyên dương, milliseconds | `10000` | Ngưỡng inclusive cho qualified read |

Chỉ chuyển một consumer sang v2 sau khi consumer đó chạy đạt toàn bộ shared fixture. Trong thời gian dual-read, event phải giữ `event_version`; không được suy đoán version từ tên topic hoặc thời điểm ingest. Rollback bằng cách trả cả hai version flag về `v1`; raw event v2 vẫn được giữ lại.

## 3. Identity, fingerprint và privacy

Identity online chuẩn là `(user_id, request_id)`. `user_id` phải do server lấy từ danh tính đã xác thực; không tin `user_id` do browser gửi.

Identity offline chuẩn là `H(salt:user_id:request_id)`, trong đó `H` là HMAC-SHA-256 và salt là secret riêng theo dataset version. Dataset/export không chứa raw `user_id` hoặc raw `request_id`; không tái sử dụng salt giữa các phạm vi dữ liệu cần unlink.

Mỗi online identity chỉ thuộc một immutable request envelope. Server tạo request fingerprint bằng SHA-256 của JSON canonical theo RFC 8785, gồm:

- Metadata `feed_source`, `model_version`, `feature_schema_version`.
- Candidate set đã sắp theo `position`; mỗi phần tử gồm `position`, `post_id`.

Mỗi request phải có `position` duy nhất và `post_id` duy nhất. Nếu cùng `(user_id, request_id)` xuất hiện với feed source, model/version, feature schema, thứ tự hoặc candidate set khác, phải từ chối toàn bộ request; không được merge một phần. Việc hash trùng không được xem là bằng nhau trước khi canonical envelope cũng bằng nhau.

Retry trên từng candidate dùng identity `(user_id, request_id, position, post_id)` và fingerprint của toàn bộ candidate row:

- Retry giống hệt trả success và không ghi thêm row.
- Retry cùng identity nhưng payload khác phải từ chối request.
- Đây là candidate retry deduplication, tách biệt với request-level collision rejection.

## 4. Required event envelope

Mọi raw event đủ điều kiện tạo recommendation label phải có:

`event_id`, `event_version`, `event_type`, `user_id`, `request_id`, `post_id`, `occurred_at`, `ingested_at`.

Trường theo loại event:

- `visible`: `viewport_ratio`.
- `view`: `continuous_visible_ms`.
- `dwell`: `dwell_ms`.
- `click`: `target`.
- Canonical actions không nhận state tùy ý từ browser; server chỉ phát event sau một state transition thành công.

`event_id` là idempotency key toàn cục. Duplicate giống hệt được trả success nhưng bỏ qua. Cùng `event_id` mà khác payload phải bị từ chối và phát collision metric.

## 5. Semantics

| Semantic | Target | Quy tắc |
|---|---:|---|
| `exposure` | chưa final | Candidate có `visible`; label window còn mở hoặc chưa có outcome |
| `click` | 1 | Người dùng chủ động mở bài từ candidate đã serve; không bắt buộc `visible` đến trước |
| `qualified_read` | 1 | `view.continuous_visible_ms >= QUALIFIED_READ_MS` hoặc `dwell.dwell_ms >= QUALIFIED_READ_MS` |
| `positive` | 1 | Active `like` hoặc comment hợp lệ |
| `strong_positive` | 1 | Active `save` hoặc `share` |
| `negative` | 0 | Có exposure, label window đã đóng và không còn outcome ưu tiên cao hơn |
| `strong_negative` | 0 | Active `hide` hoặc report hợp lệ |

So sánh qualified-read là inclusive. Với mặc định 10.000 ms, 10.000 đạt còn 9.999 không đạt. Dwell ngắn không tự tạo negative; negative chỉ được finalizer tạo sau khi label window đóng và đã có exposure. Click-before-visible vẫn hợp lệ vì click là bằng chứng hành vi trực tiếp trên candidate đã serve.

`visible` không phải positive. `implicit_skip` là label dẫn xuất, không phải event browser được phép gửi.

## 6. Precedence và reversal

Sau khi validate và deduplicate, event được xử lý ổn định theo `(occurred_at, ingested_at, event_id)`. Áp dụng state transition/reversal trước rồi lấy semantic active có độ ưu tiên cao nhất:

1. `strong_negative`
2. `strong_positive`
3. `positive`
4. `qualified_read`
5. `click`
6. `negative`
7. `exposure`

Reversal chuẩn:

- `unlike` vô hiệu active `like`.
- `unsave` vô hiệu active `save`.
- `unshare` vô hiệu active `share`.
- `unhide` vô hiệu active `hide`.

Undo không phải negative feedback. Sau undo, resolver tiếp tục xét các evidence còn active; chỉ sinh `negative` nếu có exposure và label window đã đóng. Report không reversible trong label contract; quy trình hủy report thuộc moderation/audit và phải phát một contract version mới nếu muốn thay đổi historical label.

## 7. Shared conformance fixture

Fixture dùng `event_defaults` làm envelope chung; implementation phải merge defaults với từng event trước khi validate. Ma trận khóa các trường hợp:

- Đúng ngưỡng và dưới ngưỡng một millisecond.
- Click đến trước visible.
- Long dwell/view.
- Like, save, share, hide và report.
- Unlike, unsave, unshare và unhide.
- Duplicate event giống hệt.
- Candidate retry giống hệt, request fingerprint khác, position trùng và post trùng.

TypeScript, Rust và Python phải đọc trực tiếp cùng file fixture này. Không copy case sang hằng số riêng trong từng service.

## 8. Activation gate và rollback

V2 chỉ được kích hoạt khi:

1. TS, Rust và Python đều pass shared fixture.
2. Telemetry và feature event có metric theo version và collision/rejection.
3. Dataset metadata ghi `engagement-label-v2`, flag values, threshold và offline hash algorithm.
4. Dataset builder từ chối mixed versions và conflicting request identity.

Rollback là trả `RECOMMENDATION_LABEL_VERSION=v1` và `FEATURE_EVENT_VERSION=v1`. Không xóa raw event, không đổi ý nghĩa artifact đã phát hành và không ghi đè dataset v2 bằng output v1.

## 9. Verification

```bash
python -m json.tool docs/contracts/recommendation-label-v2.json >/dev/null
python -m json.tool tests/fixtures/recommendation_telemetry/label-v2-cases.json >/dev/null
python -m pytest -q tests/test_recommendation_label_v2_contract.py
```
