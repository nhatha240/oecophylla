/* Shared shell components: Sidebar, Topbar, Avatar, PostCard, etc. */
const { useState, useMemo, useEffect, useRef } = React;

function Avatar({ author, size = 's40', square = false, showVerified = false }) {
  if (!author) return null;
  const initials = author.name.split(' ').slice(-2).map(s => s[0]).join('').toUpperCase();
  return (
    <span className={`avatar ${size} ${square ? 'sq' : ''} t-${author.tint || 'emerald'}`}>
      {initials}
      {showVerified && author.verified && (
        <span className="verified" title="Đã xác minh">
          <I.Check size={9} />
        </span>
      )}
    </span>
  );
}

function Sidebar({ active, onNav, counts = {} }) {
  const items = [
    { id: 'feed',    name: 'Trang chủ',  icon: 'Home' },
    { id: 'explore', name: 'Khám phá',   icon: 'Compass' },
    { id: 'follow',  name: 'Theo dõi',   icon: 'Users' },
    { id: 'group',   name: 'Nhóm',       icon: 'Group' },
    { id: 'saved',   name: 'Đã lưu',     icon: 'Bookmark' },
    { id: 'notif',   name: 'Thông báo',  icon: 'Bell', count: counts.notif },
    { id: 'profile', name: 'Hồ sơ',      icon: 'User' },
  ];
  return (
    <aside className="sidebar">
      <div className="brand" onClick={() => onNav('landing')} style={{ cursor: 'pointer' }}>
        <div className="brand-mark">O</div>
        <div className="brand-name">Oecophy<em>lla</em></div>
      </div>
      <nav className="nav">
        {items.map(it => {
          const Ic = I[it.icon];
          return (
              <button key={it.id} className={`nav-item ${active === it.id ? 'active' : ''}`}
                      onClick={() => onNav(it.id)}>
                <Ic size={18}/>
                <span className="top-inner-edge"></span>
                <span className="bottom-inner-edge"></span>
                <span className="top-glow"></span>
                <span className="liquid-core"></span>
                <span>{it.name}</span>
                {it.count ? <span className="count">{it.count}</span> : null}
              </button>
          );
        })}
        <div className="nav-section">Của bạn</div>
        <button className="nav-item" onClick={() => onNav('group')}>
        <span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--emerald-500)' }}/>
          AI có trách nhiệm
        </button>
        <button className="nav-item" onClick={() => onNav('group')}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--azure-500)' }}/>
          Kinh tế Việt Nam
        </button>
        <button className="nav-item" onClick={() => onNav('group')}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--amber-500)' }}/>
          Báo chí số
        </button>
      </nav>
      <div className="sidebar-foot">
        <div className="profile-card" onClick={() => onNav('profile')}>
          <Avatar author={window.DATA.AUTHORS[0]} size="s32" />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="name">Nguyễn Quỳnh Anh</div>
            <div className="handle">@quynhanh</div>
          </div>
          <I.Settings size={16} className="muted" />
        </div>
      </div>
    </aside>
  );
}

function Topbar({ crumbs, search = true, onTheme, theme, onAdmin, onNotif, notifBtnRef, right }) {
  return (
    <header className="topbar">
      {crumbs && <div className="crumbs">{crumbs}</div>}
      {search && (
        <div className="search">
          <span className="icon"><I.Search size={15}/></span>
          <input placeholder="Tìm chủ đề, tác giả, hoặc bài viết…" />
        </div>
      )}
      <div className="topbar-actions">
        {right}
        <button className="icon-btn" title="Đổi giao diện" onClick={onTheme}>
          {theme === 'dark' ? <I.Sun size={18}/> : <I.Moon size={18}/>}
        </button>
        <button className="icon-btn" title="Trung tâm thông báo" onClick={onNotif} ref={notifBtnRef} data-notif-trigger>
          <I.Bell size={18} />
          <span className="dot" />
        </button>
        {onAdmin && <button className="btn ghost sm" onClick={onAdmin} style={{ marginLeft: 6 }}>
          <I.Shield size={14}/> Khu vực quản trị
        </button>}
      </div>
    </header>
  );
}

function ModBadge({ kind, label }) {
  const icons = {
    'verified-src': 'Shield',
    'moderated': 'Check',
    'pending': 'Clock',
    'flagged': 'Flag',
    'ai': 'Sparkle',
  };
  const Ic = I[icons[kind] || 'Check'];
  return (
    <span className={`badge ${kind}`}>
      <Ic size={11} />
      {label}
    </span>
  );
}

function TopicChip({ topicId, ...rest }) {
  const t = window.DATA.TOPICS.find(x => x.id === topicId);
  if (!t) return null;
  return <span className="chip" {...rest}>#{t.name}</span>;
}

function PostCard({ post, onLike, onSave, onOpen, liked, saved, hideRecommend = false }) {
  const a = post.author;
  return (
    <article className="post" data-screen-label="Post Card">
      <header className="post-head">
        <Avatar author={a} size="s40" showVerified />
        <div className="who">
          <div className="name">
            {a.name}
            {a.verified && <I.Verified size={13} style={{ color: 'var(--verify, var(--azure-500))' }} />}
          </div>
          <div className="sub">
            {a.handle} · <I.Clock size={11}/> {post.time}
          </div>
        </div>
        <div className="right">
          <ModBadge kind={post.moderation} label={post.moderationLabel} />
          <button className="icon-btn" title="Thêm"><I.More size={16}/></button>
        </div>
      </header>

      <h3 className="post-title" onClick={onOpen}>{post.title}</h3>
      <p className="post-summary">{post.summary}</p>

      {post.image && (
        <div className="post-thumb">
          <div className="ph-img" style={{ width: '100%', height: '100%' }}>ẢNH BÌA · 16:9</div>
        </div>
      )}

      {post.link && (
        <div className="post-link-preview">
          <div className="ph-img">LINK</div>
          <div className="pl-meta">
            <span className="pl-domain"><I.ExternalLink size={10} style={{ display: 'inline', verticalAlign: -1, marginRight: 4 }}/>{post.link.domain}</span>
            <div className="pl-title">{post.link.title}</div>
          </div>
        </div>
      )}

      <div className="post-meta-row">
        {post.tags.map(t => <TopicChip key={t} topicId={t} />)}
        <span className="t-meta" style={{ marginLeft: 'auto' }}>
          <I.Eye size={12} style={{ display: 'inline', verticalAlign: -2, marginRight: 4 }}/>
          {post.stats.reads} lượt đọc
        </span>
      </div>

      {!hideRecommend && (
        <div className="recommend-line">
          <I.Sparkle size={14} />
          {post.reason}
        </div>
      )}

      <div className="post-actions">
        <button className={`post-action like ${liked ? 'active' : ''}`} onClick={onLike}>
          {liked ? <I.HeartFill size={16}/> : <I.Heart size={16}/>}
          {post.stats.likes + (liked ? 1 : 0)}
        </button>
        <button className="post-action">
          <I.Comment size={16}/> {post.stats.comments}
        </button>
        <button className="post-action">
          <I.Share size={16}/> {post.stats.shares}
        </button>
        <button className={`post-action save ${saved ? 'active' : ''}`} onClick={onSave}>
          {saved ? <I.BookmarkFill size={16}/> : <I.Bookmark size={16}/>}
          {saved ? 'Đã lưu' : 'Lưu'}
        </button>
        <span style={{ flex: 1 }} />
        <button className="post-action" title="Ẩn bài"><I.EyeOff size={16}/></button>
        <button className="post-action" title="Báo cáo"><I.Flag size={16}/></button>
      </div>
    </article>
  );
}

function Toast({ children, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 2200); return () => clearTimeout(t); }, []);
  return <div className="toast"><I.Check size={14}/> {children}</div>;
}

/* ============ Notifications popover (floating panel from bell icon) ============ */
function NotificationsPopover({ open, onClose }) {
  const [cat, setCat] = React.useState('all');
  const [readSet, setReadSet] = React.useState(new Set());
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (!ref.current) return;
      if (ref.current.contains(e.target)) return;
      // Ignore clicks on the bell that opened us (handled by toggle)
      if (e.target.closest('[data-notif-trigger]')) return;
      onClose();
    };
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const cats = [
    { id: 'all', name: 'Tất cả' },
    { id: 'Tương tác', name: 'Tương tác' },
    { id: 'Kiểm duyệt', name: 'Kiểm duyệt' },
    { id: 'Gợi ý', name: 'Gợi ý' },
  ];
  const list = window.DATA.NOTIFICATIONS.filter(n => cat === 'all' || n.cat === cat);
  const unreadCount = list.filter(n => n.unread && !readSet.has(n.id)).length;

  const tonePalette = {
    rose:   ['var(--rose-50)',   'var(--rose-500)'],
    emerald:['var(--emerald-50)','var(--emerald-500)'],
    azure:  ['var(--azure-50)',  'var(--azure-500)'],
    violet: ['var(--violet-50)', 'var(--violet-500)'],
    amber:  ['var(--amber-50)',  'var(--amber-500)'],
  };

  return (
    <>
      <div className="notif-pop-scrim" onClick={onClose} />
      <div className="notif-pop" ref={ref} data-screen-label="Notifications Popover">
        <div className="notif-pop-head">
          <div>
            <div className="notif-pop-title">Thông báo</div>
            <div className="notif-pop-sub">
              {unreadCount > 0 ? `${unreadCount} thông báo mới` : 'Bạn đã đọc hết'}
            </div>
          </div>
          <button className="btn ghost sm" onClick={() => setReadSet(new Set(list.map(n => n.id)))}>
            <I.Check size={12}/> Đánh dấu đã đọc
          </button>
        </div>

        <div className="notif-pop-tabs">
          {cats.map(c => (
            <button key={c.id} className={`notif-pop-tab ${cat === c.id ? 'active' : ''}`} onClick={() => setCat(c.id)}>
              {c.name}
            </button>
          ))}
        </div>

        <div className="notif-pop-list">
          {list.map(n => {
            const Ic = I[n.icon];
            const [bg, color] = tonePalette[n.tone];
            const isUnread = n.unread && !readSet.has(n.id);
            return (
              <div key={n.id} className={`notif-item ${isUnread ? 'unread' : ''}`}
                onClick={() => setReadSet(new Set([...readSet, n.id]))}>
                {isUnread && <span className="unread-dot" />}
                <span className="notif-icon" style={{ background: bg, color }}>
                  <Ic size={15} />
                </span>
                <div className="notif-content">
                  <div className="notif-msg">{n.msg}</div>
                  <div className="notif-time">
                    <span>{n.time}</span>
                    <span>·</span>
                    <span>{n.cat}</span>
                  </div>
                </div>
                {n.who && <Avatar author={n.who} size="s32" />}
              </div>
            );
          })}
          {list.length === 0 && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
              Không có thông báo nào trong mục này.
            </div>
          )}
        </div>

        <div className="notif-pop-foot">
          <a href="#" onClick={(e) => { e.preventDefault(); onClose(); }}>Cài đặt thông báo</a>
          <span className="t-meta">Cập nhật vừa xong</span>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { Avatar, Sidebar, Topbar, ModBadge, TopicChip, PostCard, Toast, NotificationsPopover });
