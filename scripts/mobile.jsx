/* Mobile mockup: shows the feed inside a phone frame with bottom nav */

function MobilePreview({ onBack }) {
  const [tab, setTab] = React.useState('home');
  const navs = [
    { id: 'home',   name: 'Trang chủ',  icon: 'Home' },
    { id: 'expl',   name: 'Khám phá',   icon: 'Compass' },
    { id: 'post',   name: 'Đăng',       icon: 'Plus' },
    { id: 'notif',  name: 'Thông báo',  icon: 'Bell' },
    { id: 'me',     name: 'Hồ sơ',      icon: 'User' },
  ];

  return (
    <div data-screen-label="10 Mobile" style={{ padding: '40px 32px 80px', maxWidth: 1100, margin: '0 auto' }}>
      <div className="admin-h">
        <div>
          <h2 className="serif" style={{ fontWeight: 500, fontSize: 28, letterSpacing: '-0.015em', margin: 0 }}>Xem trên di động</h2>
          <div className="sub" style={{ color: 'var(--muted)', fontSize: 13, marginTop: 4 }}>
            Bottom navigation với 5 mục chính. Composer mở dạng modal toàn màn hình.
          </div>
        </div>
        <button className="btn ghost sm" onClick={onBack}><I.ArrowLeft size={13}/> Quay lại desktop</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 32, justifyItems: 'center', marginTop: 24 }}>
        {/* Phone 1: Home feed */}
        <div>
          <div className="t-eyebrow" style={{ textAlign: 'center', marginBottom: 14 }}>Home feed</div>
          <PhoneFrame>
            <MobileHomeFeed />
            <BottomNav tab="home" navs={navs} onTab={setTab}/>
          </PhoneFrame>
        </div>
        {/* Phone 2: Detail */}
        <div>
          <div className="t-eyebrow" style={{ textAlign: 'center', marginBottom: 14 }}>Trang chi tiết bài viết</div>
          <PhoneFrame>
            <MobileArticle />
            <BottomNav tab="home" navs={navs} onTab={setTab}/>
          </PhoneFrame>
        </div>
      </div>
    </div>
  );
}

function PhoneFrame({ children }) {
  return (
    <div className="mobile-frame">
      <div className="mobile-statusbar">
        <span>9:41</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: 11 }}>
          <span>●●●●</span>
          <span style={{ marginLeft: 6 }}>5G</span>
          <span style={{ marginLeft: 6 }}>▮▮▮▯</span>
        </div>
      </div>
      <div className="mobile-content">
        {children}
      </div>
    </div>
  );
}

function BottomNav({ tab, navs, onTab }) {
  return (
    <div className="mobile-bottomnav">
      {navs.map(n => {
        const Ic = I[n.icon];
        const isPost = n.id === 'post';
        if (isPost) {
          return (
              <button key={n.id} className="mb-item" onClick={() => onTab(n.id)} style={{alignItems: 'center'}}>
                <span className="top-inner-edge"></span>
                <span className="bottom-inner-edge"></span>
                <span className="top-glow"></span>
                <span className="liquid-core"></span>
                <div className="mb-post"><Ic size={16}/></div>
              </button>
          );
        }
        return (
            <button key={n.id} className={`mb-item ${tab === n.id ? 'active' : ''}`} onClick={() => onTab(n.id)}>
            <Ic size={18}/>
            <span>{n.name}</span>
          </button>
        );
      })}
    </div>
  );
}

function MobileHomeFeed() {
  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--paper)' }}>
      {/* Header */}
      <div style={{ padding: '12px 18px', background: 'var(--paper)', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--hairline)', position: 'sticky', top: 0, zIndex: 2 }}>
        <div className="brand-mark" style={{ width: 26, height: 26, borderRadius: 8, fontSize: 16 }}>O</div>
        <div style={{ font: '500 17px var(--font-serif)', letterSpacing: '-0.01em' }}>
          Oecophy<em style={{ fontStyle: 'normal', color: 'var(--emerald-500)' }}>lla</em>
        </div>
        <button className="icon-btn" style={{ marginLeft: 'auto', width: 32, height: 32 }}><I.Search size={16}/></button>
        <button className="icon-btn" style={{ width: 32, height: 32 }}>
          <I.Bell size={16}/>
          <span className="dot"/>
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, padding: '8px 14px', overflowX: 'auto', borderBottom: '1px solid var(--hairline)', background: 'var(--paper)' }}>
        {['Dành cho bạn', 'Đang theo dõi', 'Tin mới', 'Xu hướng', 'Đã lưu'].map((t, i) => (
          <button key={i} style={{
            font: '600 12px var(--font-ui)',
            color: i === 0 ? 'var(--paper)' : 'var(--ink-2)',
            background: i === 0 ? 'var(--ink)' : 'var(--surface-2)',
            border: 0, padding: '7px 12px', borderRadius: 99, whiteSpace: 'nowrap',
          }}>{t}</button>
        ))}
      </div>

      <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {window.DATA.POSTS.slice(0, 3).map(p => (
          <article key={p.id} className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <Avatar author={p.author} size="s32" showVerified />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', gap: 4, alignItems: 'center' }}>
                  {p.author.name}
                  {p.author.verified && <I.Verified size={11} style={{ color: 'var(--azure-500)' }}/>}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{p.time} · {window.DATA.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
              </div>
              <ModBadge kind={p.moderation} label={p.moderationLabel}/>
            </div>
            <div style={{ font: '500 16px/1.25 var(--font-serif)', letterSpacing: '-0.01em', marginBottom: 6 }}>{p.title}</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45, marginBottom: p.image ? 10 : 6, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {p.summary}
            </div>
            {p.image && <div className="ph-img" style={{ aspectRatio: '16/9', borderRadius: 10, marginBottom: 10 }}>ẢNH</div>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 10px', borderRadius: 8, background: 'var(--emerald-50)', color: 'var(--emerald-700)', fontSize: 11, marginBottom: 10 }}>
              <I.Sparkle size={11}/> {p.reason}
            </div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center', borderTop: '1px solid var(--hairline)', paddingTop: 10 }}>
              <button className="post-action" style={{ padding: '6px 8px', fontSize: 12 }}><I.Heart size={14}/> {p.stats.likes}</button>
              <button className="post-action" style={{ padding: '6px 8px', fontSize: 12 }}><I.Comment size={14}/> {p.stats.comments}</button>
              <button className="post-action" style={{ padding: '6px 8px', fontSize: 12 }}><I.Share size={14}/></button>
              <span style={{ flex: 1 }}/>
              <button className="post-action" style={{ padding: '6px 8px', fontSize: 12 }}><I.Bookmark size={14}/></button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function MobileArticle() {
  const p = window.DATA.POSTS[0];
  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--paper)' }}>
      <div style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--hairline)', position: 'sticky', top: 0, background: 'var(--paper)', zIndex: 2 }}>
        <button className="icon-btn" style={{ width: 32, height: 32 }}><I.ArrowLeft size={16}/></button>
        <div style={{ flex: 1, font: '500 13px var(--font-ui)', textAlign: 'center' }}>Bài viết</div>
        <button className="icon-btn" style={{ width: 32, height: 32 }}><I.Bookmark size={16}/></button>
        <button className="icon-btn" style={{ width: 32, height: 32 }}><I.Share size={16}/></button>
      </div>
      <div style={{ padding: '20px 20px 40px' }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
          <ModBadge kind="verified-src" label="Nguồn đáng tin cậy"/>
          <span className="t-meta"><I.Clock size={11} style={{ verticalAlign: -1 }}/> 8 phút đọc</span>
        </div>
        <h1 style={{ font: '500 24px/1.15 var(--font-serif)', letterSpacing: '-0.02em', margin: '0 0 10px' }}>{p.title}</h1>
        <p style={{ font: 'italic 500 14px/1.45 var(--font-serif)', color: 'var(--muted)', margin: '0 0 16px' }}>{p.summary}</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0', borderTop: '1px solid var(--hairline)', borderBottom: '1px solid var(--hairline)' }}>
          <Avatar author={p.author} size="s40" showVerified />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{p.author.name}</div>
            <div className="t-meta">{p.author.handle} · {p.time}</div>
          </div>
          <button className="btn emerald sm">Theo dõi</button>
        </div>
        <div className="ph-img" style={{ aspectRatio: '16/9', borderRadius: 10, margin: '16px 0' }}>ẢNH MINH HỌA</div>
        <p style={{ font: '15px/1.6 var(--font-serif)', color: 'var(--ink-2)' }}>
          Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ
          lớn phổ biến với một bộ dữ liệu kiểm thử riêng…
        </p>
        <div className="why-card" style={{ marginTop: 0 }}>
          <h4 style={{ fontSize: 14 }}><I.Sparkle size={12}/> Vì sao bạn thấy bài này?</h4>
          <p style={{ fontSize: 12.5 }}>
            Bạn đã đọc nhiều bài về AI có trách nhiệm. Nguồn được xác minh, độ tin cậy cao.
          </p>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MobilePreview });
