export type Tone = 'emerald' | 'azure' | 'rose' | 'amber' | 'violet' | 'ink';

export type Author = {
  id: string;
  name: string;
  handle: string;
  tint: Tone;
  verified: boolean;
  bio: string;
  reason?: string;
};

export type Post = {
  id: string;
  author: Author;
  time: string;
  title: string;
  summary: string;
  image: boolean;
  link?: { domain: string; title: string };
  tags: string[];
  moderation: string;
  moderationLabel: string;
  reason: string;
  stats: { reads: string; likes: number; comments: number; shares: number };
  type: string;
};

export const TOPICS = [
  { id: 'ai', name: 'AI & Học máy', desc: 'Mô hình, ứng dụng, đạo đức', icon: 'Sparkle', color: 'violet' },
  { id: 'tech', name: 'Công nghệ', desc: 'Sản phẩm, công ty, xu hướng', icon: 'Cpu', color: 'azure' },
  { id: 'econ', name: 'Kinh tế', desc: 'Tài chính, vĩ mô, doanh nghiệp', icon: 'Briefcase', color: 'amber' },
  { id: 'edu', name: 'Giáo dục', desc: 'Trường học, học liệu, kỹ năng', icon: 'Book', color: 'azure' },
  { id: 'life', name: 'Đời sống', desc: 'Văn hoá, ẩm thực, du lịch', icon: 'Heart2', color: 'rose' },
  { id: 'fun', name: 'Giải trí', desc: 'Phim, âm nhạc, sự kiện', icon: 'Music', color: 'violet' },
  { id: 'sport', name: 'Thể thao', desc: 'Bóng đá, eSports, sức bền', icon: 'Trophy', color: 'amber' },
  { id: 'health', name: 'Sức khỏe', desc: 'Y học, dinh dưỡng, tinh thần', icon: 'Heart2', color: 'rose' },
  { id: 'soc', name: 'Chính trị - Xã hội', desc: 'Chính sách, cộng đồng', icon: 'Globe', color: 'ink' },
  { id: 'sci', name: 'Khoa học', desc: 'Nghiên cứu, vũ trụ, sinh học', icon: 'Atom', color: 'azure' },
  { id: 'startup', name: 'Startup', desc: 'Khởi nghiệp, gọi vốn, sản phẩm', icon: 'Rocket', color: 'emerald' },
  { id: 'code', name: 'Lập trình', desc: 'Web, hệ thống, dev tools', icon: 'Code', color: 'ink' }
];

export const AUTHORS: Author[] = [
  { id: 'a1', name: 'Nguyễn Quỳnh Anh', handle: '@quynhanh', tint: 'emerald', verified: true, bio: 'Biên tập tin công nghệ. Quan tâm AI có trách nhiệm.' },
  { id: 'a2', name: 'Trần Minh Khoa', handle: '@minhkhoa', tint: 'azure', verified: true, bio: 'Nhà sáng lập một startup giáo dục.' },
  { id: 'a3', name: 'Lê Thuỳ Dung', handle: '@thuydung', tint: 'rose', verified: false, bio: 'Cây viết về đời sống đô thị.' },
  { id: 'a4', name: 'Phạm Hữu Long', handle: '@huulong', tint: 'amber', verified: true, bio: 'Phân tích kinh tế vĩ mô.' },
  { id: 'a5', name: 'Đỗ Hoàng Nam', handle: '@hoangnam', tint: 'violet', verified: false, bio: 'Kỹ sư phần mềm. Đọc nhiều, viết ít.' },
  { id: 'a6', name: 'Bùi Khánh Linh', handle: '@khanhlinh', tint: 'ink', verified: true, bio: 'Phóng viên chính trị.' },
  { id: 'a7', name: 'Hoàng Diệu Anh', handle: '@dieuanh', tint: 'emerald', verified: false, bio: 'Sinh viên y khoa.' },
  { id: 'a8', name: 'Vũ Thái Sơn', handle: '@thaison', tint: 'azure', verified: false, bio: 'Nghiên cứu sinh AI.' }
];

export const POSTS: Post[] = [
  {
    id: 'p1',
    author: AUTHORS[0],
    time: '2 giờ trước',
    title: 'Vì sao các mô hình ngôn ngữ Việt Nam vẫn “lệch” khi đọc tiếng địa phương',
    summary: 'Phân tích 12 mô hình mở phổ biến cho thấy tỉ lệ nhận diện chính xác từ địa phương miền Trung và Tây Nguyên thấp hơn 23% so với chuẩn miền Bắc — một lỗ hổng đang được các nhóm nghiên cứu trong nước âm thầm vá.',
    image: true,
    tags: ['ai', 'tech', 'soc'],
    moderation: 'verified-src',
    moderationLabel: 'Nguồn đáng tin cậy',
    reason: 'Được đề xuất vì bạn quan tâm đến AI và Khoa học.',
    stats: { reads: '12.4K', likes: 423, comments: 68, shares: 91 },
    type: 'long'
  },
  {
    id: 'p2',
    author: AUTHORS[3],
    time: '5 giờ trước',
    title: 'Lãi suất chính sách giữ nguyên: dòng tiền sẽ đi đâu trong quý III?',
    summary: 'Ba kịch bản đang được các quỹ đầu tư nội thảo luận. Báo cáo riêng từ VinaCapital và Dragon Capital cho thấy nghiêng về kịch bản phòng thủ.',
    image: false,
    tags: ['econ'],
    moderation: 'moderated',
    moderationLabel: 'Đã kiểm duyệt',
    reason: 'Phù hợp với chủ đề Kinh tế bạn đã chọn khi đăng ký.',
    stats: { reads: '8.1K', likes: 209, comments: 34, shares: 47 },
    type: 'text'
  },
  {
    id: 'p3',
    author: AUTHORS[2],
    time: '7 giờ trước',
    title: 'Một buổi tối ở chợ đêm Tân Định: nơi Sài Gòn vẫn còn “chậm”',
    summary: 'Có những góc thành phố, đèn vàng và tiếng rao vẫn giữ nhịp riêng. Tôi đã đi 4 giờ liền, không vội, để hiểu vì sao một số người chưa muốn rời nơi này.',
    image: true,
    tags: ['life'],
    moderation: 'verified-src',
    moderationLabel: 'Bài kể chuyện',
    reason: 'Bạn vừa đọc nhiều bài về Đời sống đô thị tuần này.',
    stats: { reads: '3.2K', likes: 187, comments: 22, shares: 18 },
    type: 'long'
  },
  {
    id: 'p4',
    author: AUTHORS[1],
    time: '1 ngày trước',
    title: 'Bộ Giáo dục công bố khung kỹ năng số cho học sinh THCS',
    summary: 'Khung gồm 5 trụ cột: tư duy tính toán, an toàn thông tin, sáng tạo nội dung, đạo đức số và làm việc cùng AI. Áp dụng từ năm học 2026–2027.',
    image: false,
    link: { domain: 'Cổng thông tin Bộ GD&ĐT', title: 'Quyết định 1842/QĐ-BGDĐT về khung kỹ năng số phổ thông' },
    tags: ['edu', 'tech'],
    moderation: 'verified-src',
    moderationLabel: 'Nguồn chính thức',
    reason: 'Bạn theo dõi chủ đề Giáo dục và Lập trình.',
    stats: { reads: '15.6K', likes: 612, comments: 142, shares: 233 },
    type: 'link'
  },
  {
    id: 'p5',
    author: AUTHORS[4],
    time: '1 ngày trước',
    title: 'Tự host một mô hình 8B trên Mac Mini M4: ghi chú và những thứ tôi đã sai',
    summary: 'Tóm tắt: chạy được, nhưng quạt kêu hơn dự kiến. Bài viết chia sẻ benchmark, mức tiêu thụ điện và 3 lỗi cấu hình tôi suýt bỏ cuộc vì.',
    image: true,
    tags: ['code', 'ai'],
    moderation: 'pending',
    moderationLabel: 'Đang chờ xác minh',
    reason: 'Người bạn theo dõi đã thích bài này.',
    stats: { reads: '2.8K', likes: 145, comments: 41, shares: 12 },
    type: 'long'
  },
  {
    id: 'p6',
    author: AUTHORS[5],
    time: '2 ngày trước',
    title: 'Quy định mới về dán nhãn nội dung do AI tạo ra: ai phải chịu trách nhiệm?',
    summary: 'Dự thảo của Bộ Thông tin & Truyền thông đặt nghĩa vụ dán nhãn lên cả nền tảng phân phối lẫn người đăng tải. Doanh nghiệp đang lo ngại chi phí triển khai.',
    image: false,
    tags: ['ai', 'soc'],
    moderation: 'moderated',
    moderationLabel: 'Đã kiểm duyệt',
    reason: 'Chủ đề “AI có trách nhiệm” đang nổi trên feed của bạn.',
    stats: { reads: '21.0K', likes: 891, comments: 287, shares: 412 },
    type: 'text'
  }
];

export const TRENDING = [
  { tag: 'AI có trách nhiệm', topic: 'AI', posts: '1.2K', delta: '+18%' },
  { tag: 'Kinh tế số', topic: 'Kinh tế', posts: '842', delta: '+12%' },
  { tag: 'An toàn thông tin', topic: 'Công nghệ', posts: '610', delta: '+9%' },
  { tag: 'Khung kỹ năng số', topic: 'Giáo dục', posts: '478', delta: '+34%' },
  { tag: 'Năng lượng tái tạo', topic: 'Khoa học', posts: '321', delta: '+6%' }
];

export const SUGGEST_FOLLOW = [
  { ...AUTHORS[7], reason: 'Đăng nhiều về AI tuần này' },
  { ...AUTHORS[5], reason: '4 bạn của bạn đang theo dõi' },
  { ...AUTHORS[1], reason: 'Cùng quan tâm Giáo dục' }
];

export const TASTE = [
  { topic: 'AI & Học máy', pct: 84 },
  { topic: 'Công nghệ', pct: 71 },
  { topic: 'Khoa học', pct: 52 },
  { topic: 'Giáo dục', pct: 38 },
  { topic: 'Kinh tế', pct: 25 }
];

export const NOTIFICATIONS = [
  { id: 'n1', icon: 'HeartFill', tone: 'rose', unread: true, who: AUTHORS[3], msg: '<b>Phạm Hữu Long</b> và 12 người khác đã thích bài <b>“Vì sao các mô hình ngôn ngữ Việt Nam vẫn lệch…”</b>', time: '12 phút trước', cat: 'Tương tác' },
  { id: 'n2', icon: 'Shield', tone: 'emerald', unread: true, who: null, msg: 'Bài viết của bạn <b>“Tự host một mô hình 8B trên Mac Mini M4”</b> đã được kiểm duyệt và xuất bản công khai.', time: '1 giờ trước', cat: 'Kiểm duyệt' },
  { id: 'n3', icon: 'User', tone: 'azure', unread: true, who: AUTHORS[7], msg: '<b>Vũ Thái Sơn</b> đã bắt đầu theo dõi bạn.', time: '3 giờ trước', cat: 'Tương tác' },
  { id: 'n4', icon: 'Comment', tone: 'azure', unread: false, who: AUTHORS[5], msg: '<b>Bùi Khánh Linh</b> đã bình luận về bài <b>“Quy định mới về dán nhãn nội dung AI”</b>: “Bài phân tích cân bằng và rõ ràng…”', time: 'Hôm qua', cat: 'Tương tác' },
  { id: 'n5', icon: 'Sparkle', tone: 'violet', unread: false, who: null, msg: 'Có <b>3 chủ đề mới</b> phù hợp với bạn: <em>An toàn thông tin</em>, <em>Edge AI</em>, <em>Năng lượng tái tạo</em>.', time: 'Hôm qua', cat: 'Gợi ý' },
  { id: 'n6', icon: 'AlertCircle', tone: 'amber', unread: false, who: null, msg: 'Bình luận của bạn trong bài <b>“Lãi suất chính sách giữ nguyên”</b> được yêu cầu chỉnh sửa nhẹ trước khi đăng công khai.', time: '2 ngày trước', cat: 'Kiểm duyệt' }
];

export const topicName = (id: string) => TOPICS.find((topic) => topic.id === id)?.name ?? id;
