/* Explore, Profile, Notifications */

function Explore({ onOpenPost }) {
  const [filter, setFilter] = React.useState('all');
  const filters = [
    { id: 'all', name: 'Tất cả' },
    { id: 'week', name: 'Tuần này' },
    { id: 'pop', name: 'Phổ biến nhất' },
    { id: 'verified', name: 'Nguồn đáng tin cậy' },
    { id: 'video', name: 'Có video' },
    { id: 'long', name: 'Bài dài' },
  ];

  return (
    <div className="explore-page" data-screen-label="06 Explore">
      <section className="explore-hero">
        <div className="blob"></div>
        <div className="blob-2"></div>
        <span className="t-eyebrow" style={{ color: 'rgba(255,255,255,0.6)' }}>Khám phá</span>
        <h1 style={{ marginTop: 6 }}>Tin tức, ý tưởng và cộng đồng <em>phù hợp với bạn</em></h1>
        <p>Tìm kiếm sâu hơn theo chủ đề, tác giả hoặc nhóm. Bộ lọc giúp bạn lọc theo độ tin cậy của nguồn và thời gian xuất bản.</p>
        <div className="search-big">
          <span className="icon"><I.Search size={18}/></span>
          <input placeholder="Thử “Edge AI”, “lãi suất quý 3”, “@minhkhoa”…" />
        </div>
      </section>

      <div className="filter-row">
        {filters.map(f => (
          <button key={f.id} className={`chip ${filter === f.id ? 'active' : ''}`} onClick={() => setFilter(f.id)}>
            {filter === f.id && <I.Check size={11}/>}
            {f.name}
          </button>
        ))}
        <button className="chip outline" style={{ marginLeft: 'auto' }}>
          <I.Filter size={12}/> Bộ lọc nâng cao
        </button>
      </div>

      <div className="explore-grid">
        <div>
          <div className="section-title">
            <h3>Chủ đề đang tăng trưởng</h3>
            <a className="link">Xem tất cả <I.ArrowRight size={12}/></a>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { name: 'AI tạo sinh', sub: '2.4K bài · 14K tương tác hôm nay', delta: '+34%' },
              { name: 'An toàn thông tin', sub: '1.1K bài · 8K tương tác hôm nay', delta: '+22%' },
              { name: 'Kinh tế số', sub: '842 bài · 5K tương tác hôm nay', delta: '+18%' },
              { name: 'Edge AI', sub: '432 bài · 3K tương tác hôm nay', delta: '+62%' },
            ].map((t, i) => (
              <div key={i} className="trend-card-lg">
                <div className="ph-img">CHỦ ĐỀ</div>
                <div style={{ flex: 1 }}>
                  <h5>{t.name}</h5>
                  <div className="t-meta">{t.sub}</div>
                  <div style={{ marginTop: 8 }}>
                    <span className="delta"><I.TrendUp size={11}/> {t.delta} so với tuần trước</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="section-title">
            <h3>Bài viết nổi bật cho bạn</h3>
            <a className="link">Đổi mới <I.Refresh size={12}/></a>
          </div>
          {window.DATA.POSTS.slice(0, 3).map(p => (
            <PostCard key={p.id} post={p} onOpen={() => onOpenPost(p)} onLike={() => {}} onSave={() => {}} />
          ))}
        </div>

        <aside style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="rail-card">
            <h4><I.Sparkle size={16} className="pin"/> Chủ đề dành cho bạn</h4>
            <p className="t-meta" style={{ margin: '-6px 0 12px' }}>Dựa trên 30 ngày đọc gần đây.</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['AI có trách nhiệm', 'Edge AI', 'Khoa học dữ liệu', 'Báo chí số', 'Năng lượng tái tạo', 'Khởi nghiệp Việt', 'Edtech', 'Bảo mật'].map(t => (
                <span key={t} className="chip active">+ {t}</span>
              ))}
            </div>
          </div>

          <div className="rail-card">
            <h4><I.Shield size={16} className="pin" /> Nguồn tin đáng tin cậy</h4>
            {window.DATA.AUTHORS.filter(a => a.verified).slice(0, 4).map(a => (
              <div key={a.id} className="author-row" style={{ border: 0, padding: '10px 0', margin: 0, background: 'transparent' }}>
                <Avatar author={a} size="s40" showVerified/>
                <div className="meta">
                  <div className="n">{a.name} <I.Verified size={12} style={{ color: 'var(--azure-500)' }}/></div>
                  <div className="s">{a.bio}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="rail-card">
            <h4><I.Group size={16} className="pin" /> Nhóm gợi ý</h4>
            {[
              { name: 'AI có trách nhiệm Vietnam', m: '4.2K thành viên', tone: 'emerald' },
              { name: 'Báo chí Số', m: '2.8K thành viên', tone: 'azure' },
              { name: 'Edtech Builders', m: '1.6K thành viên', tone: 'amber' },
            ].map((g, i) => (
              <div key={i} className="suggest-item">
                <span className="avatar s40 sq" style={{ background: `var(--${g.tone}-50)`, color: `var(--${g.tone}-500)` }}>
                  <I.Group size={18}/>
                </span>
                <div className="meta">
                  <div className="n">{g.name}</div>
                  <div className="s">{g.m}</div>
                </div>
                <button className="btn ghost sm">Tham gia</button>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

/* ============ Profile ============ */
function Profile() {
  const [tab, setTab] = React.useState('posts');
  const [personalization, setPersonalization] = React.useState(true);
  const [showSensitive, setShowSensitive] = React.useState(false);
  const [activityMix, setActivityMix] = React.useState(true);

  const tabs = [
    { id: 'posts', name: 'Bài viết', count: 42 },
    { id: 'comments', name: 'Bình luận', count: 138 },
    { id: 'saved', name: 'Đã lưu', count: 12 },
    { id: 'groups', name: 'Nhóm', count: 7 },
    { id: 'activity', name: 'Hoạt động' },
  ];
  const me = window.DATA.AUTHORS[0];

  return (
    <div className="profile-page" data-screen-label="07 Profile">
      <div className="profile-cover"></div>
      <div className="profile-head">
        <Avatar author={me} size="s120" showVerified />
        <div className="profile-meta">
          <h2>
            {me.name}
            <I.Verified size={18} style={{ color: 'var(--azure-500)' }} />
          </h2>
          <div className="handle">{me.handle} · Hà Nội</div>
          <p className="bio">
            Biên tập tin công nghệ, quan tâm AI có trách nhiệm và báo chí số tại Việt Nam.
            Viết về cách công nghệ thay đổi cách chúng ta đọc tin.
          </p>
          <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
            <span className="chip active">AI</span>
            <span className="chip active">Báo chí số</span>
            <span className="chip active">Edu-tech</span>
            <span className="chip outline">+ 4</span>
          </div>
          <div className="profile-stats">
            <div><b>1.842</b> <span>người theo dõi</span></div>
            <div><b>283</b> <span>đang theo dõi</span></div>
            <div><b>42</b> <span>bài viết</span></div>
            <div><b>7</b> <span>nhóm</span></div>
          </div>
        </div>
        <div className="profile-head-actions">
          <button className="btn ghost"><I.Share size={14}/> Chia sẻ</button>
          <button className="btn primary"><I.Edit size={14}/> Chỉnh sửa hồ sơ</button>
        </div>
      </div>

      <div className="tabs" style={{ marginTop: 12 }}>
        {tabs.map(t => (
          <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.name}
            {t.count != null && <span className="count-mini">{t.count}</span>}
          </button>
        ))}
      </div>

      <div className="profile-grid">
        <div>
          {tab === 'posts' && window.DATA.POSTS.slice(0, 2).map(p => (
            <PostCard key={p.id} post={{...p, author: me}} onLike={() => {}} onSave={() => {}} onOpen={() => {}} hideRecommend/>
          ))}
          {tab === 'comments' && (
            <div className="card card-pad">
              {window.DATA.POSTS.slice(0, 3).map(p => (
                <div key={p.id} style={{ padding: '14px 0', borderTop: '1px solid var(--hairline)' }}>
                  <div className="t-meta" style={{ marginBottom: 4 }}>Bình luận trong: <b style={{ color: 'var(--ink)' }}>{p.title}</b></div>
                  <div style={{ fontSize: 14, lineHeight: 1.55 }}>
                    {p.id === 'p1' ? 'Cảm ơn nhóm đã làm khảo sát này. Có công bố dataset không ạ?' :
                     p.id === 'p2' ? 'Quan điểm phòng thủ là hợp lý trong bối cảnh hiện tại, nhưng cần xem thêm tín hiệu từ FDI…' :
                     'Bài hay, mong đọc thêm các góc nhìn từ địa phương khác nữa.'}
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'saved' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {window.DATA.POSTS.slice(0, 4).map(p => (
                <div key={p.id} className="card card-pad" style={{ cursor: 'pointer' }}>
                  <div className="t-eyebrow" style={{ marginBottom: 6 }}>{window.DATA.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
                  <div style={{ font: '500 17px/1.3 var(--font-serif)', letterSpacing: '-0.01em', marginBottom: 8 }}>{p.title}</div>
                  <div className="t-meta">{p.author.name} · {p.time}</div>
                </div>
              ))}
            </div>
          )}
          {tab === 'groups' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {['AI có trách nhiệm Vietnam', 'Báo chí Số', 'Edtech Builders', 'Khoa học mở'].map((g, i) => (
                <div key={i} className="card card-pad" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span className="avatar s56 sq t-emerald"><I.Group size={22}/></span>
                  <div>
                    <div style={{ fontWeight: 600 }}>{g}</div>
                    <div className="t-meta">{Math.floor(Math.random() * 4 + 1) * 1000} thành viên · Bạn là quản trị</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'activity' && (
            <div className="card card-pad">
              {[
                { ic: 'HeartFill', tone: 'rose', txt: <>Bạn đã thích bài <b>“Quy định mới về dán nhãn nội dung do AI tạo ra”</b></>, t: '2 giờ trước' },
                { ic: 'Bookmark', tone: 'emerald', txt: <>Bạn đã lưu bài <b>“Tự host một mô hình 8B trên Mac Mini M4”</b></>, t: '6 giờ' },
                { ic: 'Comment', tone: 'azure', txt: <>Bạn đã bình luận trong <b>“Vì sao mô hình ngôn ngữ Việt Nam vẫn lệch”</b></>, t: 'Hôm qua' },
                { ic: 'User', tone: 'violet', txt: <>Bạn đã theo dõi <b>Bùi Khánh Linh</b></>, t: '2 ngày' },
              ].map((row, i) => {
                const Ic = I[row.ic];
                return (
                  <div key={i} style={{ display: 'flex', gap: 12, padding: '14px 0', borderTop: i ? '1px solid var(--hairline)' : 0 }}>
                    <span className={`avatar s32 t-${row.tone}`}><Ic size={14}/></span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13.5 }}>{row.txt}</div>
                      <div className="t-meta" style={{ marginTop: 2 }}>{row.t}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <aside style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="taste-card">
            <h4>Hồ sơ sở thích</h4>
            <p className="hint">Các chủ đề Oecophylla nhận diện từ hành vi đọc của bạn. Bạn có thể chỉnh trực tiếp.</p>
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
              <I.Edit size={12}/> Chỉnh sở thích
            </button>
          </div>

          <div className="taste-card">
            <h4>Kiểm soát cá nhân hóa</h4>
            <p className="hint">Bạn quyết định mức độ thuật toán định hình bảng tin.</p>
            <div className="toggle-row">
              <div>
                <div className="name">Bật cá nhân hóa</div>
                <div className="desc">Tắt để chỉ thấy bài theo thời gian.</div>
              </div>
              <button className={`switch ${personalization ? 'on' : ''}`} onClick={() => setPersonalization(!personalization)} aria-label="toggle"/>
            </div>
            <div className="toggle-row">
              <div>
                <div className="name">Hiển thị nội dung nhạy cảm</div>
                <div className="desc">Đã được kiểm duyệt và gắn nhãn.</div>
              </div>
              <button className={`switch ${showSensitive ? 'on' : ''}`} onClick={() => setShowSensitive(!showSensitive)} aria-label="toggle"/>
            </div>
            <div className="toggle-row">
              <div>
                <div className="name">Trộn chủ đề ngoài sở thích</div>
                <div className="desc">Giúp tránh bong bóng thông tin.</div>
              </div>
              <button className={`switch ${activityMix ? 'on' : ''}`} onClick={() => setActivityMix(!activityMix)} aria-label="toggle"/>
            </div>
          </div>

          <div className="taste-card">
            <h4>Chủ đề đang ẩn</h4>
            <p className="hint">Bạn đã chọn không xem các chủ đề này.</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <span className="chip outline">Bóng đá <I.X size={10}/></span>
              <span className="chip outline">Giải trí <I.X size={10}/></span>
              <button className="chip outline" style={{ background: 'transparent' }}><I.Plus size={11}/> Thêm</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

/* ============ Notifications ============ */
function Notifications() {
  const [cat, setCat] = React.useState('all');
  const cats = [
    { id: 'all', name: 'Tất cả' },
    { id: 'Tương tác', name: 'Tương tác' },
    { id: 'Kiểm duyệt', name: 'Kiểm duyệt' },
    { id: 'Gợi ý', name: 'Gợi ý' },
  ];

  const list = window.DATA.NOTIFICATIONS.filter(n => cat === 'all' || n.cat === cat);
  const [readSet, setReadSet] = React.useState(new Set());

  const tonePalette = {
    rose:   ['var(--rose-50)',  'var(--rose-500)'],
    emerald:['var(--emerald-50)','var(--emerald-500)'],
    azure:  ['var(--azure-50)', 'var(--azure-500)'],
    violet: ['var(--violet-50)','var(--violet-500)'],
    amber:  ['var(--amber-50)', 'var(--amber-500)'],
  };

  return (
    <div className="notif-page" data-screen-label="08 Notifications">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
        <h2 className="serif" style={{ fontWeight: 500, fontSize: 28, letterSpacing: '-0.015em', margin: 0 }}>
          Thông báo
        </h2>
        <button className="btn ghost sm" onClick={() => setReadSet(new Set(list.map(n => n.id)))}>
          <I.Check size={12}/> Đánh dấu tất cả đã đọc
        </button>
      </div>

      <div className="tabs" style={{ marginBottom: 16 }}>
        {cats.map(c => (
          <button key={c.id} className={`tab ${cat === c.id ? 'active' : ''}`} onClick={() => setCat(c.id)}>
            {c.name}
          </button>
        ))}
      </div>

      <div className="notif-list">
        {list.map(n => {
          const Ic = I[n.icon];
          const [bg, color] = tonePalette[n.tone];
          const isUnread = n.unread && !readSet.has(n.id);
          return (
            <div key={n.id} className={`notif-item ${isUnread ? 'unread' : ''}`}
              onClick={() => setReadSet(new Set([...readSet, n.id]))}>
              {isUnread && <span className="unread-dot" />}
              <span className="notif-icon" style={{ background: bg, color }}>
                <Ic size={16} />
              </span>
              <div className="notif-content">
                <div className="notif-msg">{n.msg}</div>
                <div className="notif-time">
                  <span>{n.time}</span>
                  <span>·</span>
                  <span>{n.cat}</span>
                </div>
              </div>
              {n.who && (
                <Avatar author={n.who} size="s32" />
              )}
            </div>
          );
        })}
        {list.length === 0 && (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--muted)' }}>
            Không có thông báo nào trong mục này.
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { Explore, Profile, Notifications });
