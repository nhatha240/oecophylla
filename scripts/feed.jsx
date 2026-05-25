/* Feed / Home + Article Reader */
function Feed({ onOpenPost, toast }) {
  const [tab, setTab] = React.useState('for-you');
  const [composer, setComposer] = React.useState('');
  const [composerOpen, setComposerOpen] = React.useState(false);
  const [liked, setLiked] = React.useState(new Set(['p3']));
  const [saved, setSaved] = React.useState(new Set(['p4']));

  const tabs = [
    { id: 'for-you', name: 'Dành cho bạn', icon: 'Sparkle' },
    { id: 'follow',  name: 'Đang theo dõi', icon: 'Users' },
    { id: 'new',     name: 'Tin mới',     icon: 'Clock' },
    { id: 'trend',   name: 'Xu hướng',    icon: 'Flame' },
    { id: 'saved',   name: 'Đã lưu',      icon: 'Bookmark', count: saved.size },
  ];

  const sensitive = /chính trị|tin giả|fake/i.test(composer);

  const toggleLike = (id) => {
    const next = new Set(liked);
    if (next.has(id)) next.delete(id); else { next.add(id); toast('Đã thêm vào bài bạn thích.'); }
    setLiked(next);
  };
  const toggleSave = (id) => {
    const next = new Set(saved);
    if (next.has(id)) { next.delete(id); toast('Đã bỏ lưu.'); }
    else { next.add(id); toast('Đã lưu vào bộ sưu tập của bạn.'); }
    setSaved(next);
  };

  let posts = window.DATA.POSTS;
  if (tab === 'saved') posts = posts.filter(p => saved.has(p.id));
  if (tab === 'new')   posts = [...posts].reverse();
  if (tab === 'trend') posts = [...posts].sort((a,b) => parseInt(b.stats.shares) - parseInt(a.stats.shares));

  return (
    <div className="feed-grid" data-screen-label="04 Home Feed">
      <main className="feed-main">
        <div className="composer">
          <Avatar author={window.DATA.AUTHORS[0]} size="s40" />
          <div className="right">
            <textarea
              placeholder="Bạn muốn chia sẻ tin tức hoặc góc nhìn gì hôm nay?"
              rows={composerOpen || composer ? 3 : 1}
              value={composer}
              onChange={e => setComposer(e.target.value)}
              onFocus={() => setComposerOpen(true)}
            />
            {(composerOpen || composer) && composer.length > 12 && (
              <div className="composer-suggest">
                <span className="t-meta" style={{ marginRight: 4, alignSelf: 'center' }}>Gợi ý chủ đề:</span>
                <span className="chip outline">#Công nghệ</span>
                <span className="chip outline">#AI</span>
                <span className="chip outline">#Báo chí số</span>
                <span className="chip"><I.Plus size={11}/> Thêm</span>
              </div>
            )}
            {sensitive && (
              <div className="sensitive-hint">
                <I.AlertTriangle size={14} style={{ marginTop: 2 }} />
                <div>
                  <b style={{ display: 'block', marginBottom: 2 }}>Nội dung này có thể cần kiểm duyệt trước khi hiển thị công khai.</b>
                  Hãy đảm bảo bạn dẫn nguồn rõ ràng và tránh ngôn từ kích động. Đây chỉ là gợi ý, bài viết vẫn được lưu.
                </div>
              </div>
            )}
            <div className="composer-foot">
              <div className="composer-actions">
                <button className="icon-btn" title="Thêm ảnh"><I.Image size={16}/></button>
                <button className="icon-btn" title="Thêm liên kết"><I.Link size={16}/></button>
                <button className="icon-btn" title="Thêm chủ đề"><I.Tag size={16}/></button>
                <button className="icon-btn" title="Đăng vào nhóm"><I.Group size={16}/></button>
              </div>
              <span className="t-meta" style={{ marginLeft: 'auto' }}>
                {composer.length > 0 ? `${composer.length} ký tự` : 'Hiển thị công khai · có kiểm duyệt'}
              </span>
              <button className="btn emerald sm" disabled={!composer.trim()}>
                Đăng <I.Send size={12}/>
              </button>
            </div>
          </div>
        </div>

        <div className="tabs">
          {tabs.map(t => {
            const Ic = I[t.icon];
            return (
              <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
                <Ic size={14}/> {t.name}
                {t.count != null && <span className="count-mini">{t.count}</span>}
              </button>
            );
          })}
          <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4, padding: '0 8px', color: 'var(--muted)' }}>
            <I.Refresh size={13}/>
            <span className="t-meta">Cập nhật 12 giây trước</span>
          </span>
        </div>

        {tab === 'saved' && posts.length === 0 && (
          <div className="card card-pad" style={{ textAlign: 'center', padding: '48px 24px' }}>
            <I.Bookmark size={28} className="muted"/>
            <h4 className="serif" style={{ margin: '12px 0 4px', fontSize: 18, fontWeight: 500 }}>Chưa có bài viết nào được lưu</h4>
            <p className="muted" style={{ margin: 0 }}>Lưu bài để đọc lại sau, dù khi không có mạng.</p>
          </div>
        )}

        {posts.map(p => (
          <PostCard
            key={p.id}
            post={p}
            liked={liked.has(p.id)}
            saved={saved.has(p.id)}
            onLike={() => toggleLike(p.id)}
            onSave={() => toggleSave(p.id)}
            onOpen={() => onOpenPost(p)}
          />
        ))}

        {tab !== 'saved' && (
          <button className="btn ghost" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}>
            <I.Plus size={14}/> Xem thêm bài
          </button>
        )}
      </main>

      <aside className="rail">
        <div className="rail-card">
          <h4><I.Flame size={16} className="pin"/> Đang thịnh hành</h4>
          <div>
            {window.DATA.TRENDING.map((t, i) => (
              <div key={i} className="trend-item">
                <span className="trend-num">{i + 1}</span>
                <div>
                  <div className="trend-title">#{t.tag}</div>
                  <div className="trend-meta">
                    <span>{t.topic}</span>
                    <span>·</span>
                    <span>{t.posts} bài</span>
                    <span style={{ color: 'var(--emerald-500)', fontWeight: 600 }}>{t.delta}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rail-card">
          <h4><I.Users size={16} className="pin"/> Có thể bạn thích</h4>
          {window.DATA.SUGGEST_FOLLOW.map(a => (
            <FollowSuggestion key={a.id} author={a} />
          ))}
          <button className="btn ghost sm" style={{ width: '100%', marginTop: 12 }}>Xem thêm gợi ý</button>
        </div>

        <div className="rail-card">
          <h4><I.ChartBar size={16} className="pin"/> Sở thích đọc của bạn</h4>
          <p className="t-meta" style={{ margin: '-6px 0 14px' }}>Dựa trên 30 ngày đọc gần nhất.</p>
          <div className="taste-bars">
            {window.DATA.TASTE.map(t => (
              <div key={t.topic} className="taste-bar">
                <div className="taste-bar-head">
                  <span>{t.topic}</span>
                  <span className="pct">{t.pct}%</span>
                </div>
                <div className="taste-bar-track">
                  <div className="taste-bar-fill" style={{ width: t.pct + '%' }} />
                </div>
              </div>
            ))}
          </div>
          <button className="btn ghost sm" style={{ width: '100%', marginTop: 14 }}>
            <I.Settings size={12}/> Tinh chỉnh sở thích
          </button>
        </div>

        <div className="t-meta" style={{ textAlign: 'center', lineHeight: 1.7 }}>
          <a href="#">Điều khoản</a> · <a href="#">Bảo mật</a> · <a href="#">Cookie</a> · <a href="#">Trợ giúp</a><br/>
          © 2026 Oecophylla
        </div>
      </aside>
    </div>
  );
}

function FollowSuggestion({ author }) {
  const [followed, setFollowed] = React.useState(false);
  return (
    <div className="suggest-item">
      <Avatar author={author} size="s32" showVerified/>
      <div className="meta">
        <div className="n">{author.name} {author.verified && <I.Verified size={12} style={{ color: 'var(--azure-500)'}}/>}</div>
        <div className="s">{author.reason || author.handle}</div>
      </div>
      <button className={`btn ${followed ? 'ghost' : 'primary'} sm`} onClick={() => setFollowed(!followed)}>
        {followed ? 'Đang theo dõi' : '+ Theo dõi'}
      </button>
    </div>
  );
}

/* ============ Article Reader ============ */
function Reader({ post, onBack, toast }) {
  const [liked, setLiked] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [followed, setFollowed] = React.useState(false);
  const [commentSort, setCommentSort] = React.useState('relevant');

  if (!post) return null;
  const a = post.author;

  return (
    <div className="reader" data-screen-label="05 Article Reader">
      <div className="crumbs">
        <a href="#" onClick={e => { e.preventDefault(); onBack(); }} style={{ color: 'var(--muted)' }}>
          <I.ArrowLeft size={12} style={{ verticalAlign: -2 }} /> Quay lại bảng tin
        </a>
        {' · '} <span>{window.DATA.TOPICS.find(t => t.id === post.tags[0])?.name}</span>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <ModBadge kind={post.moderation} label={post.moderationLabel} />
        <span className="t-meta"><I.Clock size={12} style={{ verticalAlign: -2 }}/> 8 phút đọc</span>
        <span className="t-meta">· {post.time} · {post.stats.reads} lượt đọc</span>
      </div>

      <h1>{post.title}</h1>
      <p className="dek">{post.summary}</p>

      <div className="meta-row">
        <Avatar author={a} size="s56" showVerified />
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
            {a.name}
            {a.verified && <I.Verified size={14} style={{ color: 'var(--azure-500)' }} />}
          </div>
          <div className="t-meta">{a.handle} · {a.bio}</div>
        </div>
        <button className={`btn ${followed ? 'ghost' : 'emerald'} sm`} onClick={() => setFollowed(!followed)}>
          {followed ? 'Đang theo dõi' : '+ Theo dõi'}
        </button>
      </div>

      {post.image && (
        <div className="ph-img" style={{ width: '100%', aspectRatio: '16/9', borderRadius: 14, marginBottom: 28 }}>
          ẢNH MINH HỌA · 16:9
        </div>
      )}

      <div className="body">
        <p>
          Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ lớn
          phổ biến với một bộ dữ liệu kiểm thử riêng gồm 4.200 câu hội thoại có yếu tố địa phương. Kết quả khá bất ngờ:
          mặc dù điểm tổng thể trên các benchmark quốc tế khá cao, các mô hình này vẫn “lệch” khi xử lý từ ngữ vùng Bắc Trung Bộ
          và Tây Nguyên.
        </p>
        <p>
          Lỗi không nằm ở khả năng nhận diện ký tự, mà ở việc gán ngữ nghĩa. Các từ như “mô”, “tê”, “răng”, “rứa” thường bị
          gán sai vai trò trong câu, dẫn đến phản hồi mất ngữ cảnh. Trên một số tác vụ tóm tắt, độ chính xác giảm hơn 23% so
          với cùng một câu được viết theo chuẩn miền Bắc.
        </p>
        <h2>Vấn đề không chỉ là dữ liệu</h2>
        <p>
          Nhiều người sẽ nghĩ ngay đến chuyện thiếu dữ liệu huấn luyện. Đúng — nhưng chưa đủ. TS. Lê Minh Tuấn, người dẫn dắt
          nhóm, cho rằng phần lớn lỗi đến từ cách các mô hình được tinh chỉnh ưu tiên ngôn ngữ chuẩn báo chí, vốn nghiêng về
          phương ngữ miền Bắc, trong giai đoạn fine-tuning.
        </p>
        <blockquote>
          “Khi 80% dữ liệu tinh chỉnh là báo chí, chúng ta vô tình dạy mô hình rằng một số phương ngữ ‘không trang trọng đủ’.”
        </blockquote>
      </div>

      <div className="why-card">
        <h4><I.Sparkle size={14}/> Vì sao bạn thấy bài viết này?</h4>
        <p>
          Bạn đã đọc 11 bài về AI trong 30 ngày qua và tương tác nhiều với chủ đề <b>“AI có trách nhiệm”</b>.
          Bài viết này có nguồn được xác minh, độ tin cậy cao và đang nhận phản hồi tích cực từ cộng đồng mà bạn theo dõi.
        </p>
        <div className="why-tags">
          <span className="chip active">AI có trách nhiệm</span>
          <span className="chip active">Khoa học dữ liệu</span>
          <span className="chip outline">Tiếng Việt tự nhiên</span>
        </div>
      </div>

      <div className="reader-actions">
        <button className={`post-action like ${liked ? 'active' : ''}`} onClick={() => { setLiked(!liked); toast(liked ? 'Đã bỏ thích.' : 'Đã thích.'); }}>
          {liked ? <I.HeartFill size={16}/> : <I.Heart size={16}/>}
          {post.stats.likes + (liked ? 1 : 0)} lượt thích
        </button>
        <button className="post-action"><I.Comment size={16}/> {post.stats.comments} bình luận</button>
        <button className="post-action"><I.Share size={16}/> Chia sẻ</button>
        <button className={`post-action save ${saved ? 'active' : ''}`} onClick={() => { setSaved(!saved); toast(saved ? 'Đã bỏ lưu.' : 'Đã lưu.'); }}>
          {saved ? <I.BookmarkFill size={16}/> : <I.Bookmark size={16}/>}
          {saved ? 'Đã lưu' : 'Lưu'}
        </button>
        <span style={{ flex: 1 }} />
        <button className="post-action"><I.Flag size={16}/> Báo cáo</button>
      </div>

      <h3 className="serif" style={{ fontWeight: 500, fontSize: 22, margin: '32px 0 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        {post.stats.comments} bình luận
        <span style={{ display: 'inline-flex', gap: 4, fontSize: 13 }}>
          <button className={`btn sm ${commentSort === 'relevant' ? 'primary' : ''}`} onClick={() => setCommentSort('relevant')}>Liên quan nhất</button>
          <button className={`btn sm ${commentSort === 'new' ? 'primary' : ''}`} onClick={() => setCommentSort('new')}>Mới nhất</button>
        </span>
      </h3>

      <div className="composer" style={{ marginBottom: 24 }}>
        <Avatar author={window.DATA.AUTHORS[0]} size="s40" />
        <div className="right">
          <textarea placeholder="Viết bình luận của bạn… (lịch sự, có dẫn chứng nếu có thể)" rows={2}/>
          <div className="composer-foot">
            <span className="t-meta">Bình luận sẽ hiển thị công khai. Hành vi quấy rối sẽ bị ẩn tự động.</span>
            <button className="btn emerald sm" style={{ marginLeft: 'auto' }}>Đăng bình luận</button>
          </div>
        </div>
      </div>

      <Comment author={window.DATA.AUTHORS[3]} time="12 phút trước"
        body="Bài viết phân tích cân bằng. Một câu hỏi: nhóm có thử kiểm tra với fine-tuning bằng dữ liệu cộng đồng (như crowdsourcing) chưa? Có thể bù lệch nhanh hơn là chờ data sạch."
        replies={[
          { author: window.DATA.AUTHORS[0], time: '8 phút', body: 'Có anh ạ, bọn em đã thử với 4 mô hình. Cải thiện 8–11%. Đang viết phần 2.' },
        ]}
      />
      <Comment author={window.DATA.AUTHORS[5]} time="40 phút trước"
        body="“Báo chí chuẩn” không có lỗi gì, nhưng nếu trở thành tiêu chuẩn duy nhất cho fine-tuning thì đúng là vấn đề. Vote cho ý này." />

      {/* Related */}
      <h3 className="serif" style={{ fontWeight: 500, fontSize: 22, margin: '40px 0 12px' }}>
        Bài viết liên quan
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {window.DATA.POSTS.slice(1, 3).map(p => (
          <div key={p.id} className="card card-pad" style={{ cursor: 'pointer' }} onClick={() => onBack()}>
            <div className="t-eyebrow" style={{ marginBottom: 6 }}>{window.DATA.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
            <div style={{ font: '500 17px var(--font-serif)', letterSpacing: '-0.01em', lineHeight: 1.25, marginBottom: 8 }}>{p.title}</div>
            <div className="t-meta">{p.author.name} · {p.time}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Comment({ author, time, body, replies = [] }) {
  return (
    <div className="comment">
      <Avatar author={author} size="s40" showVerified/>
      <div style={{ flex: 1 }}>
        <div className="c-meta"><span className="name">{author.name}</span><span className="time">{time}</span></div>
        <div className="c-body">{body}</div>
        <div className="c-acts">
          <button><I.Heart size={12} style={{ verticalAlign: -2, marginRight: 4 }}/> 8</button>
          <button>Trả lời</button>
          <button>Báo cáo</button>
        </div>
        {replies.length > 0 && (
          <div className="replies">
            {replies.map((r, i) => (
              <div key={i} className="comment reply">
                <Avatar author={r.author} size="s32" />
                <div style={{ flex: 1 }}>
                  <div className="c-meta"><span className="name">{r.author.name}</span><span className="time">{r.time}</span></div>
                  <div className="c-body">{r.body}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { Feed, Reader });
