# Vận hành implicit feedback cho gợi ý bài viết

## Dữ liệu và điều kiện trước khi bật đọc v2

- Áp dụng migrations `20260929000022_behavior_event_topic_snapshot.sql` và `20260929000023_interaction_event_outbox.sql` trước khi chạy interaction-service hoặc feature worker bản mới. Sự kiện mới lưu `topic_snapshot` từ bài viết tại lúc ghi; sự kiện cũ có `NULL` chỉ có thể dùng chủ đề hiện tại của bài viết.
- Giữ `RANKER_MODE=heuristic` và `PREFERENCE_SCHEMA_VERSION=v1` trong khi kiểm tra vector v2. `click`, lượt đọc đủ ngưỡng (`view`/`dwell`) và `unhide` kích hoạt replay v2 từ `behavior_events`; riêng `click`, `dwell` và `unhide` có delta v1 bằng 0. Like, save, share, hide, report và comment vẫn dùng sự kiện canonical hiện có.
- Kiểm tra frontend và interaction-service cùng dùng `QUALIFIED_READ_MS`; frontend phải bật `PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED=true`. Mỗi lượt mở trang chi tiết mới gửi `metadata.visit_id` để gộp `view` và `dwell` của cùng lượt đọc.

## Replay một lần khi thay đổi logic hoặc đối soát dữ liệu cũ

1. Sao lưu hoặc ghi lại số hàng `behavior_events`, `user_preference_vectors_v2`, `source_event_count` và vài vector mẫu. Dừng mọi replica feature worker và tạm dừng job retention trong suốt replay để nguồn không bị xóa giữa lúc kiểm tra và ghi vector.
2. Xác minh phạm vi lịch sử còn trong `behavior_events` cho từng người dùng có vector v2. Chỉ còn **một** sự kiện nguồn hoặc số hàng hiện tại lớn hơn `source_event_count` đều không chứng minh lịch sử đầy đủ: job retention giữ telemetry thô 180 ngày. Nếu dữ liệu dùng để tạo vector cũ đã bị xóa, cần khôi phục từ bản lưu hoặc chủ động chấp nhận vector chỉ dựa trên phần lịch sử còn lại; không gọi đó là replay toàn bộ lịch sử.
3. Trong môi trường feature worker có `DATABASE_URL` và `REDIS_URL`, chạy `python -m app.rebuild_v2 --all`. Lệnh mặc định từ chối ghi đè vector v2 đã có. Sau khi kiểm tra nguồn và quyết định rõ cách xử lý lịch sử thiếu, dùng `python -m app.rebuild_v2 --all --replace-existing-vectors`. Có thể giới hạn bằng `--user-id <uuid>`. Lệnh phân trang theo `user_id`, cập nhật từng vector trong transaction và xóa cache liên quan sau mỗi người dùng.
4. Nếu lệnh báo người dùng không còn sự kiện nguồn, dừng rollout và điều tra retention trước khi bật v2. Không thể tái tạo chính xác phần lịch sử đã xóa chỉ từ telemetry hiện còn.
5. So sánh số hàng, `source_event_count`, vector mẫu và cache; khởi động lại worker và retention job sau khi hoàn tất để xử lý Kafka tồn đọng. Sau khi trace thực tế từ impression đến click/đọc và vector v2 đạt yêu cầu, mới cân nhắc `PREFERENCE_SCHEMA_VERSION=v2` theo từng môi trường.

Interaction-service ghi envelope vào outbox cùng transaction với behavior, rồi dispatcher gửi Kafka và chỉ đánh dấu đã gửi sau khi broker xác nhận. Dispatcher thử lại khi gửi thất bại; worker khử trùng lặp bằng `event_id` khi một envelope được gửi lại sau sự cố. Theo dõi hàng chờ `interaction_event_outbox` chưa có `sent_at`, `attempts` và `last_error`. Hàng đã gửi được xóa sau 7 ngày. Replay v2 vẫn cần thiết khi đổi logic tính điểm hoặc sửa dữ liệu lịch sử.

Redis trending chỉ cộng các sự kiện mới được worker nhận qua receipt, nên Kafka gửi lại không cộng điểm lần hai. Nếu Redis lỗi sau khi receipt đã ghi thành công, điểm trending có thể thiếu một lượt; nguồn chính `behavior_events` và vector v2 không mất sự kiện đó.
