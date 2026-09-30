# Hybrid recommendation: content + implicit collaborative filtering v1

**Status:** đề xuất để review; chưa có CF serving hoặc model được bật.

**Phạm vi:** feed cá nhân hóa của người dùng đã đăng nhập.

**Nguồn chân lý liên quan:** [engagement-label-v2](recommendation-label-v2.md), [recommendation-dataset-v2](recommendation-dataset-v2.md), [post-content-features-v1](post-content-features-v1.md), [trạng thái phát hành ML](../AI_ML_RELEASE_STATUS.md).

## CAPABILITY

Người dùng nhận một feed kết hợp bài từ tác giả họ theo dõi, bài phù hợp chủ đề/nội dung họ quan tâm và bài được gợi ý từ **mẫu tương tác tổng hợp** của những người dùng khác. Click, đọc đủ ngưỡng và tương tác chủ động tạo tín hiệu implicit khi đáp ứng điều kiện xác thực nguồn; bài mới và người dùng mới vẫn có đề xuất từ chủ đề đã chọn, nội dung và nguồn gần đây. `GET /api/v1/feed` giữ nguyên hình dạng response. Không hiện danh tính hoặc hành vi cá nhân của người dùng khác trong giải thích gợi ý; projection nội bộ vẫn chứa `user_id` và chịu chính sách truy cập, retention, xóa dữ liệu.

Đây là chức năng **hybrid** gồm ba lớp khác nhau:

1. **Content based:** so sở thích theo chủ đề và, khi có embedding hợp lệ, độ giống nội dung bài với lịch sử người dùng.
2. **Collaborative filtering (CF):** tìm bài có nhiều người đọc/tương tác cùng với các bài người dùng này thích.
3. **Policy + ranking:** chỉ lấy bài người xem được nhận, kết hợp điểm có giới hạn, rồi áp dụng freshness, safety và diversity.

## CONSTRAINTS

### Hiện trạng đã xác minh trong checkout

| Thành phần | Hiện trạng | Hệ quả cho thiết kế |
| --- | --- | --- |
| Telemetry | `behavior_events` giữ event chuẩn, thời điểm xảy ra/nhận, người dùng/bài do server xác thực; `recommendation_impressions` ghi bài **đã serve**. | Có nguồn để dựng cạnh người dùng–bài; impression đơn thuần không chứng minh bài đã được nhìn thấy. |
| Sở thích v2 | `user_preference_vectors_v2` là trọng số **chủ đề** dương/âm. | Không thể coi vector này là ma trận CF. Phải dựng projection người dùng–bài riêng. |
| Retrieval/ranking | `gather_candidates` gộp semantic/follow/topic/recent; heuristic hiện dùng topic/freshness/safety/diversity và bỏ qua `retrieval_score`. | Thêm candidate CF mà không thêm feature/điểm CF vào ranker sẽ chỉ đổi tập bài, chưa có điều khiển thứ tự rõ ràng. |
| Embedding | Contract `post-content-features-v1` đã có; semantic retrieval có flag và fallback. | Content based theo chủ đề có thể hoạt động khi embedding thiếu; không khai báo semantic đã phủ toàn bộ catalog. |
| Quan sát dữ liệu | Lần đo local trước (không phải audit DB mới) có 1.073 impression/99 request, 0 click, 0 dwell và rất ít event gắn impression; `post_content_features` khi đó trống. | Chưa có bằng chứng để train hoặc bật CF cho người dùng thật. Đo lại ở từng môi trường trước quyết định. |
| Xuất dataset | `recommendation-dataset-v2` chỉ gồm bài **đã serve và có bằng chứng exposure** từ `visible` hoặc click đã xác minh, để đánh giá reranking. | Không dùng nó để tuyên bố retrieval recall hoặc coi bài chưa có bằng chứng exposure là nhãn âm. |

Chính sách bất biến:

- Chỉ server định danh user và xác minh recommendation context. Event trùng phải được khử theo `event_id`; xử lý reversal theo [label v2](recommendation-label-v2.md). `visible` là exposure, không phải positive; không click hoặc không nhìn thấy không tự động là negative.
- Bộ lọc quyền truy cập luôn nằm **ngoài CF/model**. Hiện schema chưa có private/friend visibility: điều kiện đang có là bài `published`, tác giả active, cùng hide/report và cooldown theo người xem trong candidate retrieval. Nếu sau này có private/block, phải mở rộng policy chung trước khi CF được phép truy xuất; quan hệ của hai người dùng không tự cấp quyền xem bài.
- Mọi nguồn, kể cả cache, trending và fallback, phải kiểm tra lại eligibility theo người xem ngay trước khi trả feed. Hydration hiện tại của feed-service chỉ kiểm tra `published`; đây là việc cần sửa trước khi đưa nguồn CF vào phục vụ thật.
- Không dùng ID hay tương tác của MIND/xMIND để dựng đồ thị CF Oecophylla. Chúng là benchmark khác domain; kết quả benchmark không chứng minh chất lượng hay quyền sử dụng trong sản phẩm.
- Dữ liệu/feature offline phải có mốc quan sát: `occurred_at` **và** `ingested_at` của event, publication của bài và thời điểm feature tồn tại đều không được sau cutoff. Split theo thời gian ở cấp request; không để hành vi tương lai của user hoặc bài tương lai lọt vào quá khứ.
- Raw behavior và impression hiện có lịch retention 180 ngày. API xóa tài khoản hiện chỉ vô hiệu hóa user, không kích hoạt cascade. CF projection, aggregate, cache, outbox và artifact cần quy trình xóa/khử ảnh hưởng được kiểm chứng; không lấy FK cascade làm bằng chứng xóa đủ.

## IMPLEMENTATION CONTRACT

### 1. Trạng thái và chuyển trạng thái

| Trạng thái | Điều kiện | Kết quả người dùng |
| --- | --- | --- |
| `off` (mặc định) | Chưa có snapshot CF hợp lệ hoặc chưa qua gate. | Feed hiện tại, không có CF. |
| `shadow` | Có projection/neighbor snapshot; chỉ tính và log điểm CF. | Feed vẫn do ranker hiện tại quyết định. |
| `on` (canary rồi mở rộng) | Snapshot tươi, đủ support; offline + online gate đạt. | CF cung cấp candidate và điểm tăng cường có giới hạn. |
| `fallback` | Snapshot lỗi/cũ, thiếu seed, timeout hoặc độ hỗ trợ thấp. | Trả content/follow/topic/recent/trending theo policy hiện tại; không lỗi request vì CF. |

`COLLABORATIVE_MODE=off|shadow|on` là flag đề xuất, độc lập với `RANKER_MODE=heuristic|shadow|ml`. CF v1 không tự bật ML artifact. Mỗi snapshot có `version`, `built_at`, cửa sổ dữ liệu, code/weight version và trạng thái active được đổi atomically; cache feed theo user phải hết hạn hoặc bị invalidation khi đổi snapshot/mode.

### 2. Từ implicit event đến cạnh người dùng–bài

Tạo projection `cf_user_post_affinity` từ canonical `behavior_events`, không đọc counter tổng hợp hay `user_preference_vectors_v2` như historical truth. Đề xuất dùng cùng ý nghĩa điểm với feature worker v2: click `+1`, qualified read `+0.5`, like `+1.5`, save/share `+2.5`, comment `+1`, hide `-2`, report `-5`. Các trọng số này là **khởi điểm để thử nghiệm**, không phải nhãn đánh giá hoặc thông số đã được hiệu chuẩn. Gộp `view`/`dwell` của cùng lượt đọc một lần; cap số event lặp, áp dụng decay theo thời gian, và undo like/save/share/hide phải hoàn tác trạng thái hiện hành thay vì tạo negative mới. `hide`/`report` là hard exclusion cho chính người xem, kể cả khi điểm aggregate khác dương.

Input tối thiểu: `event_id`, `event_version`, `user_id` lấy từ server, `post_id`, `event_type`, `occurred_at`, `ingested_at`, verified `impression_id` nếu event nhận từ feed, và `visit_id`/canonical action identity nếu cần chống đếm lặp. **Trust tier cho CF graph:** client `click`, `view` và `dwell` chỉ tạo cạnh dương khi có impression đã serve được server xác minh thuộc đúng `(user_id, post_id)`; `view`/`dwell` còn phải qua ngưỡng qualified read. Hiện ingest cho phép một số telemetry không có `impression_id`, nên event null-impression không được tự động xem là verified feed engagement. Chỉ canonical like/save/share/comment do server ghi sau state transition thành công mới có thể đóng góp từ direct-entry, với provenance riêng, cap chống spam và thống kê coverage riêng. Muốn dùng click/đọc từ direct-entry phải bổ sung chứng cứ nguồn và kiểm tra chống lạm dụng trước. Chỉ cạnh **dương đạt trust tier** được dùng xây item neighbors. Cạnh âm dùng để loại trừ/hạn chế cho người dùng đó, không ghép thành “hai bài giống nhau vì cùng bị ẩn”.

Đề xuất bảng logic (tên migration chốt khi triển khai):

| Store | Khóa/trường chính | Ghi chú |
| --- | --- | --- |
| `cf_user_post_affinity` | `(user_id, post_id)`, positive/negative score, active states, last_event_at, source watermark, projection version | Có thể tái dựng từ raw còn trong retention; TTL/retention của projection không được vô hạn ngầm định. |
| `cf_item_neighbors` | `(snapshot_version, post_id, neighbor_post_id)`, similarity, distinct-user support, built_at | Chỉ top-K neighbor có support đạt ngưỡng; không xuất user ID. |
| `cf_snapshot_registry` | version, cutoff, input range/hash, weights/code version, coverage, active state | Publish atomically sau khi validate và kiểm tra xóa user. |

Event v1/v2 và raw cũ thiếu provenance phải được đo, cách ly theo version hoặc replay có giải thích; không trộn âm thầm vào một artifact. Batch rebuild và incremental update phải cho cùng kết quả với cùng cutoff/version. Khi account-erasure xảy ra: xóa projection/cache, xử lý raw/outbox theo chính sách xóa, **rebuild aggregate neighbor** để loại ảnh hưởng của user đã xóa, rồi thu hồi artifact/snapshot cũ. Một job retention phải chứng minh cả đường đi này.

### 3. Item-item CF v1 và content based

Chọn **item-item co-engagement** cho bản đầu: mỗi bài có danh sách bài lân cận theo những user đã tương tác dương với cả hai. Điểm tương đồng đề xuất:

```text
sim(i,j) = weighted_cosine(user_affinity[:,i], user_affinity[:,j])
           × distinct_common_users / (distinct_common_users + shrinkage)
cf_score(u,j) = normalized_sum over positive seed i of affinity(u,i) × sim(i,j)
```

Lọc cặp có quá ít user chung (ngưỡng `k` cấu hình và được review về privacy), giới hạn số seed/neighbor, khử bùng nổ từ bài quá phổ biến và không trả chính seed item như neighbor. Tiếp tục áp dụng hide/report/cooldown hiện có; loại vĩnh viễn mọi bài user từng click/like/save sẽ là thay đổi chính sách riêng, chưa mặc định ở v1. Dùng support và độ mới của seed/snapshot để giảm độ tin cậy. Cách này cho bài mới fallback content based dù chưa có CF edge. [Nghiên cứu item-to-item của Amazon](https://www.cs.umd.edu/~samir/498/Amazon-Recommendations.pdf) là tham khảo kiến trúc; [implicit CF của Hu–Koren–Volinsky](https://yifanhu.net/PUB/cf.pdf) là hướng thử nghiệm sau khi dữ liệu đủ dày. Chưa chọn ALS/BPR hoặc huấn luyện embedding CF cho serving v1.

Content based có hai tầng: (a) topic relevance từ sở thích khai báo và vector hành vi v2 đang dùng; (b) semantic similarity từ embedding `post-content-features-v1` khi encoder, content hash và timestamp hợp lệ. Không có embedding thì tầng (a) vẫn chạy. User mới không có hành vi dùng chủ đề đã chọn + follow/recent; bài mới không có co-engagement vẫn lấy được từ follow/topic/recent hoặc semantic khi feature tồn tại. Không tạo click giả cho cold start.

### 4. Retrieval, policy và ranking

Luồng đề xuất:

```text
behavior_events -> user-post projection -> item neighbors (versioned)
                                            |
declared topics + topic vector + content embeddings
                                            |
follow / topic / recent / semantic / CF candidates
             -> viewer-scoped eligibility -> hybrid ranking + diversity
             -> final viewer-scoped hydration -> served impression -> feedback
```

CF lấy ID từ last-N seed dương, tra neighbor snapshot active, rồi chuyển qua `candidates_for_ids` hoặc cùng predicate eligibility **trước LIMIT**. Query này hiện không bảo toàn thứ tự hoặc `retrieval_score`, nên lớp CF phải gắn lại score/support theo ID sau SQL; không tin thứ tự trả về. Giới hạn thời gian truy vấn và phần pool cho CF (mốc thử nghiệm ≤20% pool), giữ nguồn follow/topic/recent và backfill. Một bài có thể thuộc nhiều nguồn; dedup **giữ toàn bộ membership và score** thay vì “first source wins”. `source` hiển thị có thể là primary source, nhưng provenance phục vụ phân tích phải có mọi nguồn.

Ranker cần `rank-features-v3` ở Python, Rust và offline validator, giữ `topic_relevance` hiện có và thêm optional `content_score`, optional `cf_score`, `cf_support`, `cf_snapshot_version`, `source_scores`, `blend_version` và `observed_at`. Mọi giá trị phải được chuẩn hóa/clip theo contract và tính từ thông tin có trước `observed_at`. Khi CF thiếu hoặc support thấp, `cf_score` được đánh dấu **missing** và trọng số còn lại được chuẩn hóa lại; không biến missing thành zero-negative. Đề xuất điểm cuối là `base_heuristic + bounded_cf_boost × confidence(user_history, support, snapshot_age)` sau policy, rồi diversity rerank. Trọng số/giới hạn cụ thể chỉ khóa sau đánh giá. Giữ model v1/v2 cũ đọc được; không thay đổi âm thầm bộ 8 feature mà ML artifact cũ chờ đợi.

`recommendation_impressions` cần lưu snapshot và source membership/score thực sự dùng ở serving. Hiện `candidate_source` và `recommendation_candidate_events.source` chỉ là một chuỗi, trong khi một bài có thể vừa từ content vừa từ CF; mở rộng bằng JSON có version hoặc bảng con `(request_id, post_id, source)` với score và selected flag. Candidate retrieval telemetry là chẩn đoán, **không phải nhãn tương tác**. Feed cache và fallback phải log version/mode thực sự đã trả.

### 5. Bề mặt, lỗi và khả năng quan sát

- Public API giữ `GET /api/v1/feed`; không buộc frontend gửi user ID/điểm CF. Nếu có “Vì sao thấy bài này?”, copy chỉ nói về chủ đề, nội dung tương tự hoặc độ phổ biến tổng hợp khi đủ support; không lộ người dùng/cặp item support thấp.
- Nội bộ recommendation API trả model/feature snapshot version; feed-service ghi đúng snapshot sau final hydration. Mọi đường cached/trending/fallback dùng cùng viewer policy trước khi trả.
- Metrics theo mode/snapshot: warm-user/item coverage, graph sparsity, neighbor support, source overlap, candidate contribution, stale/missing snapshot, latency/p95, timeout/fallback, impression→exposure→engagement trace, qualified read/save, hide/report, catalog coverage, diversity, bài mới và ngôn ngữ. Không ghi raw user ID vào artifact/report.
- Fail closed cho quyền truy cập; fail open về **chất lượng đề xuất**: nếu CF lỗi, dùng các nguồn hợp lệ còn lại. Feed-service hiện có timeout 500 ms khi gọi recommendation API và mục tiêu feed cache miss <1.500 ms; triển khai phải đo p95 chứ không cộng một truy vấn đắt vào hot path không kiểm soát.

### 6. Đánh giá và rollout

1. **Data readiness:** chạy lại audit dữ liệu thật theo version và provenance. Đếm user/item có cạnh dương đạt trust tier, sự kiện client bị loại vì thiếu impression, số cạnh mỗi user/item, connected component, cold-start rate, tỷ lệ click/qualified read gắn impression đã serve, content feature coverage, erasure backlog. Không train nếu graph không đủ user chung hoặc label thiếu; không thay bằng MIND.
2. **Offline:** split thời gian theo request; mọi seed/neighbor/feature phải tồn tại trước request. So sánh content/heuristic với hybrid trên **cùng bài đã serve + có bằng chứng exposure** cho nDCG@10, Recall@K và bootstrap theo `request_group` hiện có; báo coverage, diversity, novelty, strong negative, cold user/item, bài tiếng Việt và confidence interval. Dataset v2 không có khóa user ổn định, nên không gọi bootstrap này là user-cluster CI. Nếu cần CI theo user, thêm `user_group` pseudonymous ổn định trong contract dataset mới sau privacy review. Một test leave-last-out của retrieval chỉ là proxy có selection bias; dataset v2 và candidate log hiện tại không hỗ trợ counterfactual retrieval recall.
3. **Shadow:** tính CF và log source/score/snapshot, nhưng không đổi feed. So parity giữa offline và serving; theo dõi trace, policy, latency, fallback, source overlap và deletion. Gate ML hiện có yêu cầu 48 giờ/10.000 request shadow; xác định gate CF cụ thể trước triển khai.
4. **Canary:** khi offline và shadow đạt, A/B ngẫu nhiên có nhóm content-only control và ≤5% traffic CF; đo CTR, qualified read, save, hide/report, coverage/diversity, p95 và fallback. Gate hiện có cho ML yêu cầu 24 giờ/5.000 request canary, p95 ≤500 ms, fallback ≤1%, errors ≤0,1%; không tự động coi đạt gate ML là đạt gate CF. Chỉ A/B mới hỗ trợ kết luận nhân quả về tăng giá trị retrieval/hybrid.
5. **Rollback:** `COLLABORATIVE_MODE=off`, đổi active snapshot hoặc invalidation cache. Dữ liệu đã ghi giữ version; không gán lại nguồn/nhãn lịch sử khi rollback.

## NON-GOALS

- Chưa thay production ranker bằng NRMS/ALS/BPR hay tuyên bố content embedding đã được backfill đầy đủ.
- Chưa cá nhân hóa bằng dữ liệu MIND/xMIND hoặc dùng benchmark đó để chứng minh gain Oecophylla.
- Chưa thêm UI riêng cho CF; feed và lời giải thích gợi ý là bề mặt người dùng.
- Chưa suy ra quyền xem bài từ người dùng tương tự, và chưa dùng bài không được serve hoặc không có bằng chứng exposure làm negative trong đánh giá.

## OPEN QUESTIONS

1. Phạm vi discovery mong muốn: mọi bài `published` đủ policy, hay ưu tiên/giới hạn bài của tác giả đã theo dõi? Hiện feed For You có discovery ngoài follow; đây là quyết định sản phẩm, không phải hệ quả của CF.
2. Chọn cửa sổ training/retention của affinity và ngưỡng `k` distinct users, seed/neighbor, snapshot freshness, quota CF sau khi xem phân phối dữ liệu thật.
3. Có cho canonical action từ direct-entry đóng góp vào CF graph bằng cùng trọng số với action từ feed không? Đề xuất ghi provenance và đo riêng trước khi gộp; client click/đọc direct-entry phải chờ cơ chế xác thực nguồn riêng.
4. Cơ chế xóa tài khoản: hard erase ngay hay lịch xóa theo chính sách? Cần chốt trước khi giữ projection/aggregate dài hơn raw telemetry.
5. Nội dung giải thích gợi ý nào được phép hiện, và có cần điều khiển cá nhân hóa/opt-out riêng không?
6. Có loại khỏi CF candidate bài đã được click/like/save trong quá khứ sau khi cooldown hết không? Policy hiện chỉ loại hide/report và visible/view trong cooldown.

## HANDOFF

**Sẵn sàng chia việc theo contract; chưa sẵn sàng bật CF `on`.** Thứ tự triển khai đề xuất:

1. Sửa final viewer-scoped eligibility trên mọi feed path và thiết kế erasure/outbox/artifact lifecycle.
2. Đo lại telemetry, dựng projection user–post idempotent/reversible + test parity/replay/retention, và backfill content feature có provenance.
3. Tạo neighbor snapshot versioned, source membership và candidate path với quota/fallback; giữ flag `off`.
4. Thêm `rank-features-v3` xuyên Python/Rust/dataset, hybrid score có giới hạn; chạy `shadow`.
5. Đánh giá theo thời gian, A/B canary, quyết định `on` theo gate và rollback đã kiểm chứng.
