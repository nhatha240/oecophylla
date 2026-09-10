# Kế hoạch thu thập log người dùng và hoàn thiện pipeline AI/ML

**Trạng thái:** Sẵn sàng để chia subagent triển khai  
**Ngày lập:** 2026-08-27  
**Phạm vi:** Oecophylla recommendation pipeline  
**Chế độ thực thi:** Shared worktree/direct mode; máy hiện tại không có GitHub CLI  

## 1. Mục tiêu

Biến hệ khuyến nghị theo luật/trọng số hiện tại thành một pipeline AI/ML có dữ liệu huấn luyện, đánh giá theo thời gian, model artifact, cơ chế so sánh với baseline và tiêu chí công bố rõ ràng.

Thứ tự ưu tiên bắt buộc:

1. Ghi impression và sự kiện xem gắn với `user_id`.
2. Sửa Precision@K và xây bộ đánh giá theo thời gian.
3. Loại bài đã hide/report/đã xem khỏi ứng viên.
4. Chuẩn hóa pipeline NLP và không tin cậy topic từ client.
5. Tạo `build_dataset.py`, `train.py`, `evaluate.py` và model artifact.
6. So sánh mô hình ML với thuật toán trọng số hiện tại.
7. Chỉ công bố hệ thống là AI/ML được huấn luyện sau khi qua release gate.

## 2. Hiện trạng cần biết trước khi thực thi

- `recommendation_api/app/ranking.py` đang chấm điểm bằng trọng số thủ công; chưa có bước fit model hoặc model artifact.
- `recommendation_api/app/evaluate.py` có lỗi Precision@K: chuyển tên topic thành tập ký tự bằng `set(topic)`.
- `backend/services/feed-service` trả feed nhưng chưa ghi các bài đã phục vụ cho từng người dùng.
- `frontend/src/lib/actions/viewTracker.ts` gọi endpoint tăng `view_count`, nhưng backend không gắn lượt xem với `user_id` và không phát event `viewed` như comment trong frontend mô tả.
- `interactions` là trạng thái hiện tại cho like/save/share/hide/report, không phải event log append-only; unlike/unsave làm mất lịch sử trạng thái trước đó.
- `nlp-worker` chỉ gán topic bằng từ khóa. Nếu client gửi `topics`, worker bỏ qua bài đó.
- `posts.safety_score` hiện mặc định `1.0`; chưa có mô hình safety thực sự.
- Trong Git hiện tại, nhiều tài liệu cũ dưới `docs/` đang được đánh dấu xóa. Các agent không được tự ý khôi phục chúng.

## 3. Phạm vi và các quyết định khóa

### 3.1 Trong phạm vi

- Log bài được server phục vụ (`served impression`) và bài thực sự nhìn thấy trên màn hình (`visible impression`).
- Event log append-only có `user_id`, `post_id`, `session_id`, `impression_id` và thời gian.
- View/dwell telemetry có chống ghi trùng.
- Đánh giá offline theo time split.
- Exclusion theo hide/report và seen cooldown.
- NLP topic do server quản lý, có version/source/confidence.
- Pipeline dataset, training, evaluation và artifact có thể chạy lặp lại.
- Chế độ `heuristic`, `ml` và `shadow` trong recommendation API.
- Metrics vận hành, retention và quy tắc bảo vệ dữ liệu.

### 3.2 Ngoài phạm vi của kế hoạch này

- Deep learning/two-tower/LLM ranking.
- Thu thập dữ liệu từ báo điện tử, crawler hoặc RSS bên ngoài.
- Tự động gỡ bài bằng mô hình safety.
- A/B testing quy mô production nhiều cohort; kế hoạch chỉ chuẩn bị shadow comparison và release gate.
- Data warehouse/feature platform độc lập.

### 3.3 Quyết định dữ liệu

1. `user_id` luôn lấy từ JWT phía server; không nhận `user_id` do client gửi.
2. Feed availability là ưu tiên: lỗi ghi impression không được làm hỏng feed. Backend phải fail-open, tăng error metric và cho phép event telemetry không có `impression_id`.
3. `served` không được coi là negative sample. Chỉ `visible impression` mới đủ điều kiện làm exposure cho dataset.
4. Event telemetry là append-only. Không xóa event cũ khi unlike/unsave.
5. Dataset chỉ gán nhãn cho impression đã qua hết label window; mặc định 24 giờ.
6. Feature dùng để train phải là feature snapshot tại thời điểm phục vụ, không lấy counter hiện tại để tránh leakage.
7. Không ghi raw JWT, cookie, email, IP hoặc nội dung bình luận đầy đủ vào telemetry.
8. Mọi model artifact phải có manifest chứa model version, feature schema, khoảng dữ liệu và metric validation.
9. `visible` chỉ là exposure: >=50% diện tích trong >=800 ms. `view` là qualified engagement: >=50% liên tục trong >=5 giây hoặc mở trang chi tiết. Không phát `visible` và `view` từ cùng một threshold.
10. `view` chỉ được coi là nhãn dương khi đạt ngưỡng dwell cấu hình, mặc định `POSITIVE_DWELL_MS=10000`, hoặc có hành vi chủ động như click/like/save/share/comment.

## 4. Hợp đồng dữ liệu mục tiêu

### 4.1 `recommendation_impressions`

Mỗi row biểu diễn một bài đã được server trả trong một trang feed.

| Cột | Ý nghĩa |
|---|---|
| `id UUID PK` | Impression ID sinh ở backend |
| `request_id UUID` | Gom các item trong cùng một feed response |
| `user_id UUID` | Lấy từ JWT |
| `post_id UUID` | Bài được phục vụ |
| `position SMALLINT` | Vị trí 0-based trong response |
| `feed_source TEXT` | cache/personalized/fallback/following/trending |
| `candidate_source TEXT` | follow/topic/recent/trending |
| `score REAL` | Điểm của ranker được dùng để sắp xếp |
| `model_version TEXT` | Ví dụ `heuristic-v1`, `logreg-20260827-001` |
| `feature_snapshot JSONB` | Feature đúng tại thời điểm phục vụ |
| `served_at TIMESTAMPTZ` | Thời điểm response được tạo |

Ràng buộc tối thiểu:

- Unique `(request_id, user_id, post_id)`.
- Index `(user_id, served_at DESC)`, `(post_id, served_at DESC)`, `(model_version, served_at DESC)`.
- `position >= 0`.

### 4.2 `behavior_events`

Event append-only cho việc xây dataset và audit hành vi recommendation.

| Cột | Ý nghĩa |
|---|---|
| `id UUID PK` | Event ID phía server |
| `client_event_id UUID UNIQUE` | Idempotency key do client tạo |
| `user_id UUID` | Lấy từ JWT |
| `post_id UUID` | Bài liên quan |
| `impression_id UUID NULL` | Liên kết impression nếu có |
| `session_id UUID NULL` | ID phiên trong `sessionStorage` |
| `event_type TEXT` | visible/view/click/dwell/like/unlike/save/unsave/share/unshare/hide/unhide/report/comment |
| `dwell_ms INTEGER NULL` | Chỉ cho dwell/view; phải nằm trong giới hạn hợp lệ |
| `metadata JSONB` | Metadata nhỏ, có allowlist |
| `occurred_at TIMESTAMPTZ` | Client time đã clamp hoặc server time |
| `ingested_at TIMESTAMPTZ` | Server ingest time |

Ràng buộc tối thiểu:

- Index `(user_id, occurred_at DESC)`, `(post_id, occurred_at DESC)`, `(impression_id)`.
- `dwell_ms` trong `[0, 1_800_000]`.
- Metadata giới hạn kích thước và key.
- Request batch giới hạn tối đa 100 event.

### 4.3 API telemetry

`POST /api/v1/interactions/events/batch` — yêu cầu đăng nhập.

Ví dụ request:

```json
{
  "events": [
    {
      "client_event_id": "uuid",
      "post_id": "uuid",
      "impression_id": "uuid-or-null",
      "session_id": "uuid",
      "event_type": "visible",
      "dwell_ms": null,
      "occurred_at": "2026-08-27T10:00:00Z"
    }
  ]
}
```

Response phải cho biết số event `accepted`, `duplicate`, `rejected`. Duplicate không phải lỗi.

Quy ước event:

- `visible`: exposure đủ 50%/800 ms; không phải positive label.
- `view`: qualified view đủ 50%/5 giây hoặc mở chi tiết; chỉ thành positive khi đạt dwell guardrail.
- `click`: người dùng chủ động mở bài từ feed.
- `dwell`: thời gian đọc tổng hợp; không phát một event cho mỗi tick.
- Telemetry endpoint chỉ nhận `visible/view/click/dwell`. Like/save/share/hide/report/comment phải được server mirror từ endpoint nghiệp vụ chuẩn; client không được tự khai một positive action qua telemetry API.

### 4.4 Feed response

Mỗi response có thêm:

- `request_id`
- `model_version`
- Mỗi item có `impression_id: UUID | null` và `position`

`impression_id = null` biểu thị backend fail-open do telemetry store tạm thời không khả dụng.

## 5. Kiến trúc đích

```text
Browser
  ├─ GET /feed ───────────────► feed-service
  │                              ├─ recommendation-api
  │                              ├─ ghi recommendation_impressions
  │                              └─ trả request_id + impression_id
  │
  └─ visible/view/dwell batch ─► interaction-service
                                 ├─ ghi behavior_events append-only
                                 └─ phát Kafka sau khi DB ghi thành công

PostgreSQL telemetry
  └─ build_dataset.py
       ├─ time split + label window
       ├─ train.py ─► model artifact + manifest
       └─ evaluate.py ─► so sánh heuristic/ML

recommendation-api
  ├─ heuristic mode
  ├─ ML mode
  └─ shadow mode
```

## 6. Dependency graph

```text
P0-T1 Telemetry contract + schema
  ├─► P0-T2 Rank feature-snapshot contract
  ├─► P1-T2 Behavior-event ingest API
  ├─► P2-T1 Temporal evaluation metrics
  ├─► P3-T1 Candidate exclusion
  └─► P5-T1 Dataset builder

P0-T2 ─► P1-T1 Feed served-impression logging
P1-T2 ─► P1-T4 Feature-worker event compatibility/idempotency
P1-T2 + P4-T1 ─► P1-T5 Legacy view cutover
P1-T1 + P1-T2 + P1-T5 ─► P1-T3 Frontend visible/view/dwell tracking

P4-T1 + P5-T1 ─► P5-T2 Train/artifact
P0-T2 + P1-T1 + P2-T1 + P3-T1 + P5-T2
  └─► P6-T1 Model serving/shadow comparison
P6-T1 ─► P7-T1 Release gate, docs, final verification
```

## 7. Các wave có thể chạy song song

| Wave | Task chạy song song | Ghi chú |
|---|---|---|
| W0 | `P0-T1` | Khóa contract và schema trước |
| W1 | `P0-T2`, `P1-T2`, `P4-T1` | Không giao cùng file; agent không sửa file kế hoạch |
| W2 | `P1-T1`, `P1-T4`, `P1-T5`, `P2-T1`, `P3-T1`, `P5-T1` | Scheduler chia thành batch theo số slot; các task không giao cùng file |
| W3 | `P1-T3`, `P5-T2` | Frontend và training pipeline không giao file |
| W4 | `P6-T1` | Cần artifact và evaluation metrics |
| W5 | `P7-T1` | Coordinator tích hợp và công bố kết quả |

## 8. Quy tắc vận hành subagent trong shared worktree

1. Mỗi subagent chỉ sở hữu các file ghi trong task của mình.
2. Không chạy `git checkout`, `git reset`, `git clean` hoặc khôi phục file bị người khác xóa.
3. Không sửa file kế hoạch này khi đang thực thi; gửi đề xuất mutation cho coordinator.
4. Không commit nếu coordinator chưa yêu cầu. Shared worktree không hỗ trợ nhiều agent đổi branch độc lập an toàn.
5. Trước khi sửa, chạy `git status --short` và đọc lại file mục tiêu để nhận thay đổi mới của agent khác.
6. Khi cần sửa file thuộc task khác, gửi handoff cho owner; không tự mở rộng ownership.
7. Mỗi task phải báo: file đã đổi, migration/API contract đã thêm, lệnh test đã chạy và phần chưa xác minh.
8. Coordinator là owner mặc định của các file giao nhau như `compose.yaml`, README/tài liệu tổng hợp và final integration fixes. Ngoại lệ đã khóa: P6-T1 được sửa phần artifact mount của compose/Helm trước khi bàn giao lại cho P7-T1; hai task này chạy tuần tự.

---

# Phase 0 — Khóa contract và nền dữ liệu

## P0-T1 — Telemetry schema, API contract và test fixture

**Phụ thuộc:** Không.  
**Chặn:** Tất cả task thu thập log, dataset và temporal evaluation.  
**Mức ưu tiên:** Critical.  
**Khuyến nghị agent:** Strong/reviewer-capable vì quyết định schema khó đổi về sau.

### Context brief

Repo chưa có impression table và chưa có event log append-only. Task này chỉ tạo nền tảng dữ liệu và contract; chưa thay đổi hành vi feed/frontend.

### Ownership

- Tạo `migrations/20260827000013_recommendation_telemetry.sql`.
- Tạo `docs/contracts/recommendation-telemetry-v1.md` nếu thư mục/file chưa tồn tại.
- Tạo fixture SQL/JSON dưới `tests/fixtures/recommendation_telemetry/` nếu repo cho phép; không sửa test của service khác.

### Công việc

1. Tạo `recommendation_impressions` và `behavior_events` đúng mục 4.
2. Không dùng PostgreSQL enum cho `event_type`; dùng `TEXT` + check constraint hoặc validation application để dễ mở rộng.
3. Chọn hành vi FK khi xóa user/post phù hợp quyền xóa dữ liệu; ghi quyết định trong contract.
4. Thêm index cho time-range query và user history.
5. Định nghĩa feature snapshot v1:
   - `topic_relevance`
   - `freshness`
   - `safety_score`
   - `candidate_source`
   - `author_affinity` nếu có, nếu chưa có phải ghi `null`
   - các score `heuristic_score`, `ml_score` khi tương ứng
6. Định nghĩa idempotency, clock-skew clamp, batch limit và maximum metadata size.
7. Thêm SQL fixture minh họa served → visible → dwell → positive action.

### Verification

```bash
docker compose up -d postgres
docker compose run --rm migrate
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d recommendation_impressions"
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d behavior_events"
```

### Exit criteria

- Migration chạy trên DB rỗng và DB hiện có.
- Insert duplicate `client_event_id` được xử lý theo contract.
- Query theo `user_id + time` dùng index phù hợp.
- Contract không nhận `user_id` từ client.

### Rollback

Chỉ rollback migration trên môi trường chưa có dữ liệu thật. Khi đã có telemetry production, dùng forward migration; không drop table.

## P0-T2 — Rank feature-snapshot contract từ recommendation API tới feed-service

**Phụ thuộc:** `P0-T1`.  
**Chặn:** `P1-T1`, `P6-T1`.  
**Chạy song song với:** `P1-T2`, `P4-T1`.  
**Mức ưu tiên:** Critical.

### Context brief

Recommendation response hiện chỉ có `post_id`, `score`, `source`, `reason`; feed-service không thể tự biết đúng các feature ranker đã dùng. Task này khóa và triển khai contract truyền feature snapshot/model version, nhưng chưa ghi impression DB.

### Ownership

- `recommendation_api/app/schemas.py`
- `recommendation_api/app/ranking.py`
- `recommendation_api/app/main.py`
- Test contract/ranking dưới `recommendation_api/tests/`
- `backend/services/feed-service/src/recommendation.rs`
- Test decode contract dưới `backend/services/feed-service/tests/`

### Contract bắt buộc

Mỗi recommendation item phải có structured `features` v1:

```json
{
  "schema_version": "rank-features-v1",
  "topic_relevance": 0.42,
  "freshness": 0.81,
  "safety_score": 1.0,
  "candidate_source": "topic",
  "is_followed_author": false,
  "author_affinity": null,
  "heuristic_score": 0.47,
  "ml_score": null
}
```

Response top-level phải có `model_version`, ví dụ `heuristic-v1`. Field không dùng phải là `null`, không được tự bịa giá trị ở feed-service.

### Công việc

1. Tạo Pydantic/Rust type rõ ràng, không dùng JSON blob vô kiểu trên network contract.
2. Tính `topic_relevance`, `freshness`, safety và heuristic score đúng một lần trong recommendation API.
3. `model_version` phản ánh ranker thực sự tạo thứ tự trả về.
4. Feed client decode và giữ nguyên snapshot; không tính lại feature.
5. Version feature schema để dataset/trainer reject schema không tương thích.
6. Với following/trending/fallback không đi qua recommendation API, P1-T1 sẽ tạo snapshot tối thiểu với field không có là `null`; contract phải cho phép điều này.

### Tests bắt buộc

- Snapshot value khớp các component dùng để tính heuristic score.
- Multi-topic relevance đúng.
- Rust client decode đủ field/version.
- Missing required schema version bị reject rõ ràng.
- Nullable unavailable feature không bị thay bằng `0` gây sai nghĩa.

### Verification

```bash
cd recommendation_api
pytest -q tests/test_ranking.py tests/test_health.py
cd ../backend
cargo test -p feed-service
```

### Exit criteria

- Feed-service nhận được model version và immutable feature snapshot từ recommendation API.
- Không duplicate feature-engineering logic giữa Python ranker và Rust feed-service.
- P1-T1 có đủ dữ liệu để persist impression đúng tại serving time.

### Rollback

Giữ client decode tương thích response cũ trong một cửa sổ chuyển tiếp; model version mặc định chỉ được dùng khi response cũ được phát hiện và phải ghi metric compatibility.

---

# Phase 1 — Thu thập impression và hành vi người dùng

## P1-T1 — Ghi served impression trong feed-service

**Phụ thuộc:** `P0-T2`.  
**Chạy song song với:** `P1-T4`, `P1-T5`, `P2-T1`, `P3-T1`, `P5-T1`.  
**Mức ưu tiên:** Critical.

### Context brief

Feed hiện hydrate và trả item nhưng không lưu lịch sử phục vụ. Task này ghi một batch impression cho đúng những item thực sự có trong response sau hydrate, kể cả feed từ cache/fallback/following/trending.

### Ownership

- `backend/services/feed-service/src/types.rs`
- `backend/services/feed-service/src/repo.rs`
- `backend/services/feed-service/src/handlers.rs`
- `backend/services/feed-service/src/cache.rs` nếu cached item cần mang snapshot/model version.
- Test mới/chỉnh sửa chỉ dưới `backend/services/feed-service/tests/`
- Nếu cần metric: file feed-service hoặc common metric chỉ sau khi coordinator xác nhận ownership.

### Công việc

1. Sinh `request_id` mới cho từng feed page response.
2. Sinh `impression_id` cho từng item sau hydrate; position phải theo thứ tự trả về.
3. Batch insert impression để tránh N+1 query.
4. Persist nguyên `model_version` và feature snapshot nhận từ recommendation API; không tính lại feature trong Rust.
5. Với following/trending/fallback, tạo snapshot tối thiểu từ dữ liệu tại serving time và để feature không có là `null`.
6. Thêm `request_id`, `model_version`, `impression_id`, `position` vào response schema.
7. Áp dụng cho personalized, cache, fallback, following và trending.
8. Fail-open khi insert lỗi:
   - Feed vẫn trả thành công.
   - `impression_id = null`.
   - Ghi structured error và tăng counter.
9. Không ghi impression cho post bị hydrate loại khỏi response.

### Tests bắt buộc

- Một response 3 item tạo đúng 3 row với cùng `request_id`.
- Position đúng sau khi hydrate loại một post.
- Cache/fallback vẫn ghi impression mới cho mỗi request.
- Personalized snapshot khớp byte-for-byte/field-for-field với contract ranker; cache không làm mất model version.
- DB telemetry lỗi không làm feed trả 5xx.
- `user_id` trong DB đúng với JWT, không nhận từ query/body.

### Verification

```bash
cd backend
cargo test -p feed-service
cargo check --workspace
```

### Exit criteria

- Mọi item trả về có impression persisted hoặc `impression_id = null` khi fail-open.
- Không có per-item insert loop tới DB.
- Response cũ vẫn tương thích ngoài các field bổ sung.

### Rollback

Feature flag `IMPRESSION_LOGGING_ENABLED=false`; không rollback schema.

## P1-T2 — Behavior-event ingest API append-only

**Phụ thuộc:** `P0-T1`.  
**Chạy song song với:** `P0-T2`, `P4-T1`.  
**Mức ưu tiên:** Critical.

### Context brief

`interactions` hiện là bảng trạng thái, không giữ full history. Task này thêm endpoint authenticated để nhận visible/view/dwell event, ghi append-only và có thể phát Kafka sau khi DB thành công.

### Ownership

- `backend/services/interaction-service/src/handlers.rs`
- `backend/services/interaction-service/src/repo.rs`
- `backend/services/interaction-service/src/main.rs`
- `backend/services/interaction-service/src/events.rs`
- `backend/services/interaction-service/tests/`
- `envoy/envoy.yaml` chỉ nếu route hiện tại không chuyển `/api/v1/interactions/events/batch` đúng service.

### Công việc

1. Thêm `POST /api/v1/interactions/events/batch`.
2. Lấy user từ cookie/JWT; bỏ qua hoặc reject mọi `user_id` trong payload.
3. Validate event type, UUID, time, dwell range, batch size và metadata allowlist.
   Endpoint batch chỉ chấp nhận `visible`, `view`, `click`, `dwell`.
4. Batch insert với `ON CONFLICT (client_event_id) DO NOTHING`.
5. Xác nhận `impression_id` nếu có thuộc đúng user/post; nếu không khớp thì reject event đó.
6. Với qualified `view`, tăng `posts.view_count` đúng một lần theo `client_event_id` trong cùng transaction, nhưng chỉ khi `BEHAVIOR_VIEW_COUNTER_ENABLED=true`.
7. Trả `accepted`, `duplicate`, `rejected` và lỗi theo index của item; không làm hỏng cả batch vì một item sai.
8. Phát Kafka envelope tương thích contract P1-T4 sau commit. Chỉ qualified `view` map sang `event_type="viewed"`; `visible` và `dwell` không tự tăng user preference. DB là source of truth khi Kafka tạm lỗi.
9. Thêm rate limit và metrics accepted/duplicate/rejected/error.
10. Trong cùng task, mirror các thay đổi trạng thái thành công từ endpoint like/unlike/save/unsave/share/unshare/hide/unhide/report/comment sang `behavior_events` append-only. Chỉ ghi khi canonical action thực sự thay đổi trạng thái; dùng event ID phía server để retry không tạo lịch sử giả.

### Tests bắt buộc

- Không auth → 401.
- Payload giả user khác không thể ghi event cho user đó.
- Retry cùng `client_event_id` không tăng view hai lần.
- Impression của user/post khác bị reject.
- Batch hỗn hợp trả đúng accepted/duplicate/rejected.
- Kafka lỗi không xóa DB event đã ghi.
- `visible` không tăng view counter và không phát `viewed` preference event.
- `view` chưa đủ dwell guardrail bị reject hoặc chỉ lưu telemetry theo contract, không trở thành positive signal.
- Client gửi `like/save/report` qua telemetry endpoint bị reject; canonical action endpoint mới có quyền tạo các event đó.
- Like → unlike và save → unsave tạo đúng lịch sử append-only trong khi bảng `interactions` vẫn phản ánh trạng thái hiện tại.

### Verification

```bash
cd backend
cargo test -p interaction-service
cargo check --workspace
```

### Exit criteria

- Event log append-only, idempotent và gắn user từ JWT.
- Không lưu raw cookie/JWT/IP.
- Existing like/save/share/hide/report endpoint không bị regression.

### Rollback

Tắt route bằng config/feature flag; giữ dữ liệu đã thu thập.

## P1-T3 — Frontend visible/view/dwell tracking

**Phụ thuộc:** `P1-T1`, `P1-T2`, `P1-T5`.  
**Chạy song song với:** `P5-T2`.  
**Mức ưu tiên:** Critical.

### Context brief

Frontend đã có IntersectionObserver 50% trong 800 ms nhưng endpoint hiện chỉ tăng counter vô danh. Task này chuyển tracker sang contract telemetry mới và duy trì trải nghiệm fail-silent.

### Ownership

- `frontend/src/lib/actions/viewTracker.ts`
- `frontend/src/lib/components/FeedList.svelte`
- `frontend/src/lib/components/PostCard.svelte` chỉ nếu cần truyền telemetry metadata.
- `frontend/src/lib/types.ts`
- `frontend/src/routes/post/[id]/+page.server.ts`
- `frontend/src/routes/post/[id]/+page.svelte` nếu cần tracker phía browser cho direct-entry detail.
- Test frontend tương ứng dưới `frontend/src/` hoặc `frontend/e2e/`.

### Công việc

1. Cập nhật `FeedResponse`/`FeedItem` type với request/model/impression fields.
2. Tạo `session_id` bằng UUID trong `sessionStorage`; không dùng fingerprint.
3. Khi item hiển thị >=50% trong >=800 ms, chỉ gửi `visible` idempotent.
4. Chỉ gửi qualified `view` sau khi item hiển thị >=50% liên tục trong >=5 giây hoặc user mở trang chi tiết; không dùng cùng trigger với `visible`.
5. Gửi `click` khi người dùng chủ động mở bài từ feed.
6. Đo dwell bằng monotonic timer; gửi khi item rời viewport, component destroy hoặc page hidden.
7. Batch event trong thời gian ngắn để giảm request; flush bằng `fetch(..., {keepalive: true})`.
8. Mỗi event có `client_event_id`; retry giữ nguyên ID.
9. Nếu `impression_id = null`, vẫn gửi event với post/session để không mất hoàn toàn dữ liệu.
10. Telemetry failure không hiển thị lỗi cho user và không chặn navigation.
11. Gỡ hoặc sửa comment sai nói endpoint cũ đã phát `viewed` event.
12. Bỏ lời gọi tăng view cũ từ server load trang chi tiết; direct-entry detail phải phát qualified view từ browser và có thể để `impression_id=null`.

### Tests bắt buộc

- Chưa đủ 800 ms không gửi visible.
- Đủ 800 ms nhưng chưa đủ 5 giây chỉ gửi visible, không gửi view.
- Một item chỉ gửi một visible và một qualified view trong một page session.
- Click được gắn đúng impression/request context.
- Dwell được clamp và flush khi destroy.
- Retry không sinh client event ID mới.
- Missing impression vẫn gửi event hợp lệ.
- Direct-entry post detail không gọi legacy counter và vẫn ghi qualified view gắn user khi đăng nhập.

### Verification

```bash
cd frontend
pnpm test
pnpm run check
pnpm exec playwright test e2e/nav.spec.ts
```

### Exit criteria

- Có thể truy vết feed response → impression → visible/view/dwell bằng ID.
- Không tăng view trùng khi request retry.
- Không làm thay đổi UI hoặc gây lỗi người dùng khi telemetry backend down.

### Rollback

Đặt `PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED=false`, sau đó làm theo rollback P1-T5: disable behavior counter trước khi enable lại legacy counter. Không chạy hai tracker tăng counter đồng thời.

## P1-T4 — Kafka envelope, feature-worker compatibility và event idempotency

**Phụ thuộc:** `P1-T2`.  
**Chạy song song với:** `P1-T1`, `P1-T5`, `P2-T1`, `P3-T1`, `P5-T1`.  
**Mức ưu tiên:** High.

### Context brief

Feature worker hiện chỉ hiểu envelope legacy có `data.user_id/post_id` và các event như `viewed`, `liked`. Event `visible`, `view`, `dwell` mới sẽ bị bỏ qua hoặc có nguy cơ apply lại khi Kafka replay. Task này khóa mapping và đảm bảo preference update idempotent.

### Ownership

- `workers/feature_store_worker/app/main.py`
- `workers/feature_store_worker/app/features.py`
- `workers/feature_store_worker/tests/`
- Tạo `migrations/20260827000015_feature_event_receipts.sql` nếu dùng receipt table.
- Chỉ chỉnh `backend/services/interaction-service/src/events.rs` qua handoff với owner P1-T2; không sửa đồng thời.

### Công việc

1. Chốt Kafka envelope telemetry v1 có `event_id`, `event_type`, `occurred_at`, `producer`, `data.user_id`, `data.post_id`, `data.client_event_id`.
2. Mapping:
   - DB `view` đủ điều kiện → Kafka `viewed`;
   - `visible` và `dwell` không cộng preference;
   - like/save/share/hide/report/comment giữ mapping hiện tại.
3. Dedupe preference update theo Kafka `event_id` bằng receipt ghi cùng transaction với vector update.
4. Kafka replay/crash sau DB commit không cộng vector lần hai.
5. Không dùng dwell raw để cộng lặp; nếu sau này dùng dwell, phải bucket/cap thành đúng một derived event.
6. Trending update phải ghi rõ là approximate; nếu chưa dedupe trending thì không dùng nó làm ground-truth training label.
7. Thêm metric applied/duplicate/unknown event.

### Tests bắt buộc

- Envelope `viewed` mới cập nhật preference đúng một lần.
- Replay cùng event ID không đổi vector.
- Visible/dwell không đổi vector.
- Legacy liked/saved event vẫn hoạt động.
- Unknown event được đếm và bỏ qua an toàn.

### Verification

```bash
cd workers/feature_store_worker
pytest -q
```

### Exit criteria

- Online preference không mất view signal và không double-apply khi replay.
- Contract backend producer/worker được test bằng cùng fixture JSON.

### Rollback

Tắt derived `viewed` Kafka publish; behavior_events trong DB vẫn là source of truth để rebuild sau.

## P1-T5 — Cắt đường view cũ, ngăn double count

**Phụ thuộc:** `P1-T2`, `P4-T1` phải hoàn tất trước nếu cùng sửa content handler.  
**Chạy song song với:** `P1-T1`, `P1-T4`, `P2-T1`, `P3-T1`, `P5-T1`.  
**Chặn:** `P1-T3`.  
**Mức ưu tiên:** High.

### Context brief

Endpoint cũ `POST /api/v1/posts/{id}/view` tăng counter không idempotent. Nếu tracker mới và endpoint cũ cùng hoạt động, một lượt đọc có thể bị đếm hai lần. Task này chuẩn bị cutover có feature flag và rollout order rõ ràng.

### Ownership

- `backend/services/content-service/src/handlers.rs`
- `backend/services/content-service/src/repo.rs`
- `backend/services/content-service/src/main.rs` hoặc config tương ứng.
- Test content-service liên quan.
- Không sửa frontend; P1-T3 là owner frontend.

### Công việc

1. Thêm `LEGACY_VIEW_COUNTER_ENABLED`, có hành vi rõ khi false: endpoint cũ trả 204 nhưng không tăng counter.
2. P1-T2 dùng `BEHAVIOR_VIEW_COUNTER_ENABLED`; hai flag không được cùng true sau cutover.
3. Rollout order bắt buộc:
   - deploy behavior API với counter mới disabled;
   - deploy frontend tracker mới;
   - xác minh event ingest;
   - đồng thời disable legacy counter và enable behavior counter;
   - theo dõi duplicate/view-rate metrics.
4. Không xóa route cũ ngay để client cũ không nhận 404.
5. Ghi runbook rollback flag mà không mất behavior log.

### Tests bắt buộc

- Legacy flag false không tăng counter.
- Legacy flag true giữ hành vi tương thích trước cutover.
- Contract của hai feature flag được test/document rõ; P7-T1 chịu trách nhiệm validation trên deployment config để không bật đồng thời.

### Verification

```bash
cd backend
cargo test -p content-service
```

### Exit criteria

- Có đúng một owner tăng `posts.view_count` tại một thời điểm rollout.
- Client cũ không crash khi legacy counter bị disable.

### Rollback

Disable behavior counter trước, sau đó enable legacy counter; không bật đồng thời.

---

# Phase 2 — Sửa metric và đánh giá theo thời gian

## P2-T1 — Precision@K đúng, temporal split và metric library

**Phụ thuộc:** `P0-T2` để tránh sửa chồng `schemas.py`; pure metric unit tests có thể chuẩn bị trên fixture.  
**Chạy song song với:** `P1-T1`, `P1-T4`, `P1-T5`, `P3-T1`, `P5-T1`.  
**Mức ưu tiên:** High.

### Context brief

Evaluation hiện dùng topic proxy, có bug với topic nhiều ký tự và `ctr_simulation` không phải CTR thật. Task này tách metric thuần khỏi DB, hỗ trợ time cutoff và công bố sample size.

### Ownership

- `recommendation_api/app/evaluate.py`
- `recommendation_api/app/schemas.py`
- Tạo `recommendation_api/app/metrics.py`
- `recommendation_api/tests/test_evaluate.py`
- Tạo/chỉnh test metric dưới `recommendation_api/tests/`

### Công việc

1. Viết regression test cho topic `business`, `technology`, `ai`; test phải fail với `set(topic)` hiện tại.
2. Sửa Precision@K để so sánh tập topic với tập topic.
3. Tạo pure functions cho Precision@K, Recall@K, NDCG@K, hit-rate, catalog coverage và topic diversity.
4. Bổ sung `sample_users`, `sample_impressions`, `cutoff_at`, `label_window_hours` vào output.
5. Temporal evaluation:
   - train history trước cutoff;
   - validation impressions sau cutoff;
   - chỉ chấm row đã qua label window;
   - không dùng event tương lai để tạo feature.
6. Thay `ctr_simulation` bằng `ctr_observed` khi có impression log; giữ field cũ dạng deprecated nếu cần tương thích.
7. `fallback_rate` phải lấy từ impression `feed_source`, không hard-code 0/1 theo candidate availability.
8. Với dataset chưa đủ, trả trạng thái `insufficient_data`, không tạo metric gây hiểu nhầm.

### Tests bắt buộc

- Bộ ví dụ nhỏ có metric tính tay.
- Không chia cho 0.
- Không dùng impression chưa hết label window.
- Temporal boundary không rò rỉ event tương lai.
- Fallback rate khớp fixture.

### Verification

```bash
cd recommendation_api
pytest -q tests/test_ranking.py tests/test_diversity.py tests/test_evaluate.py
```

### Exit criteria

- Metric library độc lập DB và có test tính tay.
- Precision@K bug được khóa bằng regression test.
- API không gọi score proxy là CTR thật.

### Rollback

Giữ endpoint version cũ trong thời gian chuyển tiếp nếu consumer đang phụ thuộc schema; không rollback regression fix.

---

# Phase 3 — Candidate exclusion và trải nghiệm feed

## P3-T1 — Loại hide/report/seen khỏi candidate pool

**Phụ thuộc:** `P0-T1`; seen filtering đầy đủ cần event từ Phase 1.  
**Chạy song song với:** `P1-T1`, `P1-T4`, `P1-T5`, `P2-T1`, `P5-T1`.  
**Mức ưu tiên:** High.

### Context brief

Candidate retrieval hiện lấy follow/topic/recent nhưng không loại nội dung người dùng đã hide/report hoặc vừa xem. Task này áp dụng exclusion nhất quán cho mọi source.

### Ownership

- `recommendation_api/app/features.py`
- `recommendation_api/app/settings.py`
- Tạo/chỉnh test candidate query dưới `recommendation_api/tests/`
- Chỉ sửa `recommendation_api/app/main.py` nếu cần truyền exclusion context.

### Công việc

1. Tạo exclusion query dùng chung:
   - `hide` hiện hành;
   - đã report;
   - visible/view trong seen cooldown.
2. Thêm setting `SEEN_COOLDOWN_DAYS`, mặc định 7; không loại vĩnh viễn bài chỉ vì đã xem.
3. Áp dụng cho follow, topic, recent và mọi retrieval source bổ sung sau này.
4. Không chỉ lọc sau `LIMIT`, vì có thể làm candidate pool quá nhỏ; exclusion phải nằm trong SQL trước limit.
5. Không loại bài chỉ được server served nhưng chưa visible.
6. Loại post không published và post của user bị ban theo chính sách hiện có.
7. Ghi source/exclusion metrics để biết pool giảm bao nhiêu.

### Tests bắt buộc

- Hidden/report không xuất hiện ở bất kỳ source nào.
- Seen trong 7 ngày bị loại; seen ngoài cooldown có thể quay lại.
- Served nhưng chưa visible không bị loại.
- Không ảnh hưởng candidate của user khác.
- Cold-start vẫn có recent candidates.

### Verification

```bash
cd recommendation_api
pytest -q
```

### Exit criteria

- Exclusion diễn ra trong retrieval SQL trước limit.
- Không tái đề xuất ngay nội dung user đã phản hồi tiêu cực.
- Candidate pool vẫn có fallback cho cold-start.

### Rollback

Setting `SEEN_COOLDOWN_DAYS=0` tắt seen filtering; hide/report filtering không được tắt.

---

# Phase 4 — Chuẩn hóa NLP và quyền sở hữu topic

## P4-T1 — Server-owned topic pipeline, versioning và reprocessing

**Phụ thuộc:** Không phụ thuộc telemetry; có thể chạy từ W1.  
**Chạy song song với:** `P0-T2`, `P1-T2`.  
**Mức ưu tiên:** High.

### Context brief

Client hiện có thể gửi `topics` khi tạo bài và NLP worker bỏ qua bài đã có topic. Điều này làm feature có thể bị thao túng. NLP hiện chỉ substring-match sau NFKC/lowercase.

### Ownership

- `backend/services/content-service/src/handlers.rs`
- Test content-service liên quan.
- `workers/nlp_worker/app/infer.py`
- `workers/nlp_worker/app/keywords.py`
- `workers/nlp_worker/app/kafka_consumer.py`
- `workers/nlp_worker/app/settings.py`
- `workers/nlp_worker/tests/`
- Tạo `workers/nlp_worker/app/reprocess.py`
- Tạo `migrations/20260827000014_topic_provenance.sql` nếu cần cột provenance.

### Công việc

1. Vẫn nhận field `topics` để tương thích request cũ nhưng mặc định ignore phía server.
2. Chỉ cho admin/import job tin cậy ghi topic qua đường riêng có kiểm soát, nếu thực sự cần.
3. Lưu `topic_source`, `topic_confidence`, `nlp_version`, `topic_updated_at` hoặc metadata tương đương.
4. NFKC + lowercase + whitespace normalization + URL/HTML stripping.
5. Dùng phrase/token boundary để tránh keyword ngắn khớp bên trong từ khác.
6. Chuẩn hóa taxonomy; map alias về topic canonical.
7. Worker xử lý lại khi `nlp_version` cũ, không chỉ khi `topics` rỗng.
8. Thêm CLI reprocess theo batch/cursor, idempotent và có dry-run.
9. Không tuyên bố có safety scoring; giữ `safety_score=1.0` cho đến task riêng trong tương lai.

### Tests bắt buộc

- Client gửi topic giả không thể bypass inference.
- Keyword ngắn không match sai substring.
- Tiếng Việt có/không dấu theo chính sách được test rõ.
- Reprocess version cũ đúng một lần.
- `general` fallback và multi-topic vẫn hoạt động.

### Verification

```bash
cd workers/nlp_worker
pytest -q
cd ../../backend
cargo test -p content-service
```

### Exit criteria

- Mọi topic dùng cho recommendation có source và version.
- Client thường không điều khiển topic hệ thống.
- Có thể reprocess toàn bộ corpus an toàn.

### Rollback

Config tạm `ALLOW_CLIENT_TOPICS=true` chỉ dành cho migration/import có kiểm soát; không bật mặc định.

---

# Phase 5 — Dataset, training và model artifact

## P5-T1 — Tạo `build_dataset.py` với time split và leakage guard

**Phụ thuộc:** `P0-T1`; fixture đủ để phát triển trước khi telemetry production có dữ liệu.  
**Chạy song song với:** `P1-T1`, `P1-T4`, `P1-T5`, `P2-T1`, `P3-T1`.  
**Mức ưu tiên:** High.

### Context brief

Dataset phải bắt đầu từ visible impressions, nối các positive/negative event trong label window và dùng feature snapshot tại served time. Không dùng current post counters làm historical features.

### Ownership

- Tạo thư mục `ai_pipeline/`.
- Tạo `ai_pipeline/build_dataset.py`.
- Tạo `ai_pipeline/config.py`, `ai_pipeline/schemas.py` nếu cần.
- Tạo `ai_pipeline/requirements.txt`.
- Tạo `ai_pipeline/tests/test_build_dataset.py` và fixtures riêng.
- Không sửa `recommendation_api/` trong task này.

### Công việc

1. CLI tối thiểu:

```bash
python -m ai_pipeline.build_dataset \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-20T00:00:00Z \
  --label-window-hours 24 \
  --output artifacts/datasets/dataset.parquet
```

2. Chỉ lấy impression có event `visible`.
3. Chỉ finalize sample nếu `visible_at + label_window <= extraction_time`.
4. Định nghĩa label v1; `visible` tuyệt đối không phải positive:
   - positive mạnh: save/share;
   - positive: click, qualified view có dwell >= `POSITIVE_DWELL_MS`, like/comment;
   - negative mạnh: hide/report;
   - negative: visible nhưng không có positive trong label window.
5. Một impression là một sample; retry event không nhân đôi sample.
6. Dùng feature snapshot; reject row thiếu feature schema bắt buộc hoặc đánh dấu version.
7. Split theo thời gian, không random split:
   - train;
   - validation;
   - test holdout mới nhất.
8. Xuất Parquet cùng metadata JSON: query window, row counts, class balance, feature schema version, code version nếu có.
9. Không xuất PII; user/post IDs chỉ dùng cho group/audit và có tùy chọn hash/drop ở artifact cuối.

### Tests bắt buộc

- Served nhưng không visible không thành negative.
- Visible đơn thuần không thành positive; view dưới dwell threshold không làm positive.
- Impression chưa qua label window không vào dataset.
- Event sau label window không đổi label.
- Future feature không xuất hiện trong train row.
- Duplicate telemetry không nhân row.
- Time split không overlap.

### Verification

```bash
python -m pytest ai_pipeline/tests/test_build_dataset.py -q
python -m ai_pipeline.build_dataset --help
```

### Exit criteria

- Dataset reproducible từ cùng DB snapshot/config.
- Metadata đủ để audit nguồn và thời gian dữ liệu.
- Leakage guards có unit tests.

### Rollback

Dataset là artifact tái tạo được; xóa artifact lỗi, không sửa raw logs.

## P5-T2 — Tạo `train.py`, artifact manifest và test inference

**Phụ thuộc:** `P5-T1`, feature schema của `P4-T1` ổn định.  
**Chạy song song với:** `P1-T3`; hai task không giao file.  
**Mức ưu tiên:** High.

### Context brief

Model v1 nên đơn giản, giải thích được và chạy CPU. Baseline ML đề xuất là Logistic Regression trên feature numeric/categorical; ranking dùng xác suất positive làm score. Có thể thay bằng LightGBM ở iteration sau mà không đổi artifact contract.

### Ownership

- `ai_pipeline/train.py`
- `ai_pipeline/model.py`
- `ai_pipeline/artifact.py`
- `ai_pipeline/tests/test_train.py`
- Cập nhật `ai_pipeline/requirements.txt`
- Thư mục output mẫu `artifacts/models/` phải được `.gitignore`; chỉ commit manifest mẫu nhỏ nếu cần.

### Công việc

1. Fit preprocessing + Logistic Regression trong một sklearn Pipeline.
2. Categorical unknown phải xử lý được; numeric missing có imputation rõ ràng.
3. Dùng seed cố định và ghi seed vào manifest.
4. Không fit trên test holdout.
5. Artifact gồm:
   - serialized pipeline;
   - `manifest.json`;
   - feature schema/version;
   - data windows;
   - dependency versions;
   - validation metrics;
   - checksum.
6. CLI:

```bash
python -m ai_pipeline.train \
  --dataset artifacts/datasets/dataset.parquet \
  --output artifacts/models/logreg-v1
```

7. Fail nếu dataset quá nhỏ, chỉ có một class hoặc schema sai; không tạo artifact giả thành công.
8. Thêm load-and-predict smoke test bằng process mới.
9. Không serialize raw training rows hoặc PII vào artifact.

### Tests bắt buộc

- Train deterministic trên fixture.
- Unknown category inference không crash.
- Schema mismatch fail rõ ràng.
- Corrupt checksum bị từ chối.
- Single-class/insufficient sample không tạo artifact.

### Verification

```bash
python -m pytest ai_pipeline/tests/test_train.py -q
python -m ai_pipeline.train --help
```

### Exit criteria

- Artifact load được độc lập và tạo score `[0,1]`.
- Manifest đủ để tái tạo và audit.
- Không có test data leakage.

### Rollback

Không overwrite artifact cũ; mỗi version immutable. Rollback bằng cách trỏ config về version trước hoặc heuristic.

---

# Phase 6 — Phục vụ model và so sánh baseline

## P6-T1 — ML ranker, shadow mode và `evaluate.py`

**Phụ thuộc:** `P0-T2`, `P1-T1`, `P2-T1`, `P3-T1`, `P4-T1`, `P5-T2`.  
**Chạy song song với:** Không nên sửa recommendation API song song ở wave này.  
**Mức ưu tiên:** High.

### Context brief

Recommendation API phải giữ heuristic làm fallback. ML được bật theo mode, artifact được load một lần khi startup và mọi impression phải ghi đúng model version/feature snapshot.

### Ownership

- Tạo `recommendation_api/app/model_ranker.py`.
- `recommendation_api/app/main.py`
- `recommendation_api/app/ranking.py`
- `recommendation_api/app/schemas.py`
- `recommendation_api/app/settings.py`
- Test recommendation API liên quan.
- `recommendation_api/requirements.txt`
- `recommendation_api/requirements.runtime.txt`
- `recommendation_api/Dockerfile`
- `ai_pipeline/evaluate.py`
- `ai_pipeline/tests/test_evaluate.py`
- Phần cấu hình/mount artifact của `compose.yaml` và Helm chart; P7-T1 review lại shared infra sau khi P6 hoàn tất.
- Không sửa frontend/feed-service ngoài contract handoff đã thống nhất; gửi yêu cầu cho owner nếu thiếu field.

### Công việc

1. Thêm config `RANKER_MODE=heuristic|ml|shadow`, mặc định `heuristic`.
2. Load/checksum artifact một lần khi startup; không load mỗi request.
3. Thêm runtime dependency tối thiểu để load sklearn/joblib artifact; khóa version tương thích với trainer.
4. Không bake model artifact thay đổi thường xuyên vào image. Local compose dùng read-only mount; production dùng artifact volume/init mechanism có checksum.
5. `ml` dùng predicted probability làm base score rồi diversity rerank.
6. `shadow` vẫn trả heuristic order nhưng tính cả ML score để ghi snapshot/so sánh.
7. Model load/predict lỗi phải fallback heuristic, ghi metric và structured log.
8. Response phải trả model version thật được dùng để xếp hạng.
9. Tạo `ai_pipeline/evaluate.py` so sánh cùng một temporal holdout:
   - heuristic;
   - ML;
   - Precision@K, Recall@K, NDCG@K, hit-rate, coverage, diversity;
   - số user/impression và confidence interval nếu đủ mẫu.
10. Không dùng observed action của test row làm input feature.
11. Xuất report JSON + Markdown có config, artifact checksum và kết luận `win`, `no_regression`, `inconclusive` hoặc `fail`.

### Tests bắt buộc

- Heuristic mode không cần artifact.
- ML mode dùng đúng artifact/model version.
- Shadow không đổi thứ tự heuristic.
- Artifact lỗi fallback không gây 5xx.
- Container image có đủ runtime dependency và đọc artifact read-only từ path cấu hình.
- Baseline và ML chấm trên cùng holdout.
- Report insufficient data không tuyên bố ML thắng.

### Verification

```bash
cd recommendation_api
pytest -q
cd ..
python -m pytest ai_pipeline/tests/test_evaluate.py -q
python -m ai_pipeline.evaluate --help
```

### Exit criteria

- Có thể chuyển mode bằng config và rollback tức thì về heuristic.
- Comparison report tái tạo được.
- Impression log ghi đúng model version và feature scores.

### Rollback

Đặt `RANKER_MODE=heuristic`; giữ artifact và telemetry để điều tra.

---

# Phase 7 — Release gate và công bố

## P7-T1 — Privacy, observability, full verification và tài liệu công bố

**Phụ thuộc:** Tất cả task trước.  
**Owner:** Coordinator/integration agent duy nhất.  
**Mức ưu tiên:** Critical trước khi gọi hệ thống là trained AI/ML.

### Context brief

Task này không thêm thuật toán mới. Nó kiểm tra toàn bộ pipeline, xử lý handoff còn lại, đặt retention/monitoring và quyết định có đủ bằng chứng để công bố hay không.

### Ownership

- `compose.yaml`, Helm values/templates nếu cần config/artifact mount.
- Prometheus/Grafana telemetry metrics.
- README/tài liệu trạng thái còn tồn tại tại thời điểm triển khai.
- CI/Makefile target cho dataset/train/evaluate smoke.
- Integration tests và final compatibility fixes.
- Không khôi phục các file docs đang bị xóa nếu chưa có yêu cầu của user.

### Công việc

1. Cấu hình retention:
   - raw telemetry theo chính sách dự án;
   - aggregate lâu hơn;
   - user deletion xóa/anonymize dữ liệu theo quyết định P0.
2. Metrics tối thiểu:
   - impression insert success/failure;
   - events accepted/duplicate/rejected;
   - telemetry lag;
   - candidate exclusion count;
   - model load/predict/fallback;
   - feed source/fallback rate;
   - dataset row/class balance.
3. Alert cho impression logging failure, model fallback spike và event reject spike.
4. Chạy migrations, backend/frontend/Python tests và end-to-end smoke.
5. Thêm top-level Makefile targets để verification không phụ thuộc thư mục hiện tại, tối thiểu `test-ai-pipeline`, `smoke-ai-telemetry`, `evaluate-ai`.
6. Kiểm tra một trace mẫu:
   - feed request;
   - persisted impression;
   - frontend visible/view/dwell;
   - dataset row;
   - model score/version.
7. Chạy comparison trên temporal holdout.
8. Xác minh cutover view counter: legacy và behavior counter không cùng được bật.
9. Release gate:
   - `NDCG@10` ML không thấp hơn baseline trong ngưỡng đã thống nhất;
   - diversity/coverage không giảm quá guardrail;
   - negative-action proxy không xấu hơn;
   - sample size đủ; nếu không đủ ghi `inconclusive`;
   - không có leakage/privacy critical finding;
   - rollback heuristic đã smoke test.
10. Chỉ sửa tuyên bố tài liệu thành “mô hình ML được huấn luyện” nếu toàn bộ gate pass. Nếu chưa pass, dùng câu: “hệ khuyến nghị heuristic có pipeline thu thập dữ liệu và thử nghiệm ML”.

### Verification

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
make test
cd backend && cargo test --workspace
cd ../frontend && pnpm test && pnpm run check
cd ../recommendation_api && pytest -q
cd ../workers/feature_store_worker && pytest -q
cd ../nlp_worker && pytest -q
cd ../../ && python -m pytest ai_pipeline/tests -q
```

Thêm một smoke command do P7 tạo, ví dụ:

```bash
make smoke-ai-telemetry
make test-ai-pipeline
make evaluate-ai
```

### Exit criteria

- Full trace và rollback đã được chứng minh.
- Không còn metric giả được gọi là CTR/Precision thật.
- Báo cáo comparison được lưu cùng artifact manifest.
- Tuyên bố sản phẩm phản ánh đúng bằng chứng.

### Rollback

- `RANKER_MODE=heuristic`.
- Tắt client telemetry nếu gây sự cố, nhưng không drop raw logs.
- Roll forward migration khi schema đã chứa dữ liệu.

---

## 9. Ma trận ownership để tránh xung đột

| Task | File/module sở hữu chính | Không được tự sửa |
|---|---|---|
| P0-T1 | migration 13, telemetry contract/fixture | service implementation |
| P0-T2 | recommendation response/rank snapshot, Rust recommendation client | DB persistence, frontend |
| P1-T1 | feed-service persistence/cache/response | interaction-service, frontend, recommendation feature logic |
| P1-T2 | interaction-service, Envoy route nếu cần | feed-service, frontend |
| P1-T3 | frontend tracker/types/feed components | backend services |
| P1-T4 | feature-store-worker, migration 15 | feed/frontend, producer ngoài handoff |
| P1-T5 | legacy content-service view path | frontend, feature worker |
| P2-T1 | recommendation evaluate/metrics/schema tests | candidate queries, ranker serving |
| P3-T1 | recommendation features/settings/tests | evaluate/metrics, frontend |
| P4-T1 | content-service topic input, nlp-worker, migration 14 | recommender telemetry |
| P5-T1 | ai_pipeline dataset modules | recommendation_api |
| P5-T2 | ai_pipeline training/artifact modules | recommendation_api |
| P6-T1 | model serving + ai_pipeline evaluate | feed/frontend trừ handoff |
| P7-T1 | shared infra/docs/integration | feature code trừ integration fix |

## 10. Definition of Done toàn chương trình

- Mỗi item feed phục vụ có `request_id`, model version và impression persisted hoặc trạng thái fail-open rõ ràng.
- Visible/qualified-view/dwell event có user server-derived, idempotency và session linkage; visible không tự trở thành positive label.
- Có thể dựng dataset time-split mà không dùng served-only làm negative và không leakage.
- Hide/report/seen exclusion có test.
- Client không điều khiển topic recommendation mặc định.
- Có artifact immutable + manifest + checksum.
- ML và heuristic được chấm trên cùng temporal holdout.
- Recommendation API luôn rollback được về heuristic.
- Chỉ tuyên bố trained AI/ML khi release gate pass; thiếu dữ liệu phải ghi `inconclusive`.

## 11. Anti-pattern cấm

- Random train/test split cho dữ liệu recommendation có thời gian.
- Dùng counter hiện tại làm feature cho impression quá khứ.
- Coi mọi served item không click là negative.
- Phát `visible` và positive `view` từ cùng một visibility threshold.
- Bật đồng thời legacy view counter và behavior-event view counter.
- Tin `user_id`, `model_version` hoặc score từ client.
- Log raw cookie/JWT/email/IP vào training data.
- Ghi một DB query cho mỗi impression item.
- Tăng view counter trước khi idempotency check.
- Gọi normalized ranking score là CTR.
- Bật ML làm mặc định khi artifact thiếu/corrupt hoặc comparison chưa qua gate.
- Để nhiều subagent sửa cùng một file trong cùng wave.

## 12. Plan mutation protocol

Khi phát hiện contract cần đổi:

1. Agent dừng phần phụ thuộc trực tiếp và gửi đề xuất cho coordinator.
2. Ghi rõ: lý do, task bị ảnh hưởng, migration/API compatibility và rollback.
3. Coordinator chọn một trong bốn hành động:
   - **Insert:** thêm task mới trước task bị chặn.
   - **Split:** tách task quá lớn thành hai owner/file set riêng.
   - **Reorder:** đổi dependency/wave nhưng không cho chạy khi contract chưa khóa.
   - **Abandon:** bỏ hướng triển khai và ghi lý do.
4. Chỉ coordinator cập nhật file kế hoạch và dependency graph.
5. Không sửa migration đã chạy trên shared environment; thêm forward migration.

## 13. Handoff template cho mỗi subagent

```text
Task ID:
Kết quả:
Files changed:
Contract/migration changes:
Tests run + result:
Checks not run:
Risks/open questions:
Handoff needed from/to task:
```
