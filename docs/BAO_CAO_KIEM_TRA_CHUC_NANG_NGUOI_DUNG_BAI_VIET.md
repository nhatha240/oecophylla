# Báo cáo kiểm tra chức năng Người dùng và Bài viết

> Báo cáo lịch sử ngày 31/08. Trạng thái hiện tại, các regression mới và giới hạn xác minh nằm trong [review 08/09](PROJECT_REVIEW_STATUS.md).

- Ngày cập nhật: 31/08/2026 (Asia/Ho_Chi_Minh)
- Phạm vi: source hiện tại và Docker Compose tại `http://localhost:8080`
- Kết luận: **13/13 chức năng trong phạm vi đã đạt**

## 1. Tổng hợp kết quả

| Nhóm | Chức năng | Trạng thái | Kết quả chính |
|---|---|---:|---|
| Người dùng | Đăng ký | ✅ Đạt | Đã sửa lỗi salt Argon2 gây `500` ngẫu nhiên; kiểm thử 256 salt và smoke auth đều đạt. |
| Người dùng | Đăng nhập | ✅ Đạt | Đăng nhập đúng trả `200`; sai thông tin trả `401`; refresh/logout hoạt động. |
| Người dùng | Hồ sơ cá nhân | ✅ Đạt | Xem và cập nhật tên, bio, sở thích và avatar; chỉ chủ tài khoản được sửa. |
| Người dùng | Avatar | ✅ Đạt | Hỗ trợ upload JPEG/PNG/WebP tối đa 5 MiB, kiểm tra MIME, đuôi file và magic bytes; URL nhập tay chỉ chấp nhận HTTPS. |
| Người dùng | Follow | ✅ Đạt | Follow idempotent, ngăn tự follow và cập nhật đúng trạng thái. |
| Người dùng | Unfollow | ✅ Đạt | Unfollow trả `204` và cập nhật trạng thái về chưa theo dõi. |
| Bài viết | Đăng | ✅ Đạt | Tạo bài có validation nội dung, media, tags và phát event. |
| Bài viết | Sửa | ✅ Đạt | Đã có `PUT/PATCH`, kiểm tra owner/admin, validation, phát event cập nhật và trang UI sửa bài. |
| Bài viết | Xóa | ✅ Đạt | Chỉ owner/admin được xóa; đọc lại bài đã xóa trả `404`. |
| Bài viết | Like | ✅ Đạt | Like/unlike idempotent, không tăng bộ đếm khi gọi lặp. |
| Bài viết | Comment | ✅ Đạt | Tạo, reply một cấp và xóa bình luận hoạt động. |
| Bài viết | Share | ✅ Đạt | Ghi nhận share idempotent; UI hỗ trợ Web Share và fallback clipboard. |
| Bài viết | Bookmark | ✅ Đạt | Lưu/bỏ lưu idempotent; bài xuất hiện đúng trong danh sách đã lưu. |

## 2. Các lỗi đã khắc phục trong đợt này

### 2.1 Đăng ký: lỗi Argon2 `500` ngẫu nhiên

- Thay cách tự chuyển đổi salt bằng `SaltString::encode_b64`, tương thích trực tiếp với crate Argon2.
- Thêm regression test tạo và xác minh password hash qua 256 salt ngẫu nhiên.
- Smoke test trực tiếp qua Envoy xác nhận đăng ký, đăng nhập, refresh và logout đều thành công.

### 2.2 Avatar: bổ sung upload file

- Endpoint mới: `PUT /api/v1/users/{id}/avatar` với `multipart/form-data`.
- Endpoint đọc ảnh: `GET /api/v1/users/{id}/avatar`.
- Chỉ chủ tài khoản được upload; kiểm tra quyền trước khi đọc toàn bộ file.
- Giới hạn 5 MiB; chỉ cho JPEG, PNG và WebP.
- Kiểm tra đồng thời MIME, phần mở rộng và chữ ký đầu file để ngăn file giả mạo; SVG bị từ chối.
- Ảnh được lưu trong bảng `user_avatars`; response có `Cache-Control: immutable` và `X-Content-Type-Options: nosniff`.
- Trường `avatar_url` cũ vẫn tương thích nhưng chỉ nhận HTTPS, không có khoảng trắng và tối đa 2048 ký tự.
- Trang `/settings` có bộ chọn file, kiểm tra phía client, upload và cập nhật preview.

### 2.3 Sửa bài viết: bổ sung API và UI

- `PUT/PATCH /api/v1/posts/{id}` nhận `content`, `media_urls` và `tags`.
- Chỉ chủ bài hoặc admin được sửa; non-owner trả `403`.
- Validation: nội dung sau trim dài `1..4000`, tối đa 6 media HTTPS và tối đa 8 tags.
- Update dùng câu lệnh SQL có bind parameter và cập nhật `updated_at`.
- Phát envelope `content.updated` để worker NLP có thể xử lý lại nội dung.
- Frontend có nút sửa cho chủ bài và trang `/post/{id}/edit`.

### 2.4 ESLint 9

- Bổ sung flat config `eslint.config.js` cho TypeScript và Svelte.
- `npm run lint` chạy thành công với **0 lỗi**; còn 9 warning legacy không chặn quality gate.

## 3. Bằng chứng kiểm thử

| Hạng mục | Kết quả |
|---|---|
| Unit test Rust cho content/user | ✅ `13/13` đạt (`7` content, `6` user). |
| Regression test Argon2 | ✅ `1/1` đạt, chạy 256 salt ngẫu nhiên. |
| Auth smoke qua Envoy | ✅ `1/1` đạt: register/login/refresh/logout. |
| Avatar integration | ✅ `1/1` đạt: owner upload, non-owner bị từ chối, đọc đúng bytes/headers, file giả bị từ chối. |
| Post edit integration | ✅ `1/1` đạt: owner sửa thành công, non-owner `403`, body rỗng `400`. |
| Frontend unit test | ✅ `30/30` đạt. |
| Frontend API test | ✅ `9/9` đạt, gồm upload avatar và update post. |
| Svelte check | ✅ 0 lỗi, 0 cảnh báo. |
| ESLint 9 | ✅ 0 lỗi, 9 warning. |
| Frontend production build | ✅ Đạt. |
| Playwright luồng sửa bài | ✅ `1/1` đạt. |

## 4. Ghi chú vận hành và bảo mật

- Migration mới: `20260831000018_user_avatars.sql`.
- Cần chạy migration trước khi đưa `user-service` mới lên môi trường khác.
- Avatar hiện lưu trong PostgreSQL để cung cấp luồng upload hoàn chỉnh. Khi lưu lượng hoặc kích thước dữ liệu tăng, nên chuyển blob sang object storage/CDN nhưng giữ nguyên contract URL.
- ESLint còn 9 warning từ mã legacy; không ảnh hưởng build nhưng nên xử lý dần.
- `npm install` báo 10 lỗ hổng trong dependency tree (3 low, 5 moderate, 1 high, 1 critical). Cần chạy một đợt audit riêng và kiểm tra breaking change trước khi nâng dependency; không nên dùng `npm audit fix --force` tự động.

## 5. Release gate

Phạm vi Người dùng/Bài viết có thể qua release gate khi pipeline triển khai:

1. áp dụng migration `20260831000018_user_avatars.sql`;
2. build lại `auth-service`, `user-service`, `content-service` và frontend từ cùng commit;
3. chạy lại auth smoke, avatar integration, post-edit integration, frontend test/check/lint/build;
4. xác nhận 9 ESLint warning được chấp nhận là non-blocking cho bản phát hành này.
