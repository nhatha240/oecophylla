/* Tailwind-styled shared shell: Avatar, Sidebar, Topbar, PostCard */
const { useState: useStateTw, useEffect: useEffectTw } = React;
const G = window.G;
const I = window.I;
const DATA = window.DATA;

const tintMap = {
  emerald: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-700/30 dark:text-emerald-300',
  rose:    'bg-rose-100 text-rose-700 dark:bg-rose-700/30 dark:text-rose-300',
  amber:   'bg-amber-100 text-amber-700 dark:bg-amber-700/30 dark:text-amber-300',
  azure:   'bg-blue-100 text-blue-700 dark:bg-blue-700/30 dark:text-blue-300',
  violet:  'bg-violet-100 text-violet-700 dark:bg-violet-700/30 dark:text-violet-300',
  ink:     'bg-ink text-white',
};
const sizeMap = {
  s24: 'w-6 h-6 text-[10px]',
  s32: 'w-8 h-8 text-[12px]',
  s40: 'w-10 h-10 text-[14px]',
  s56: 'w-14 h-14 text-[18px]',
  s80: 'w-20 h-20 text-[26px]',
  s120:'w-[120px] h-[120px] text-[40px]',
};

function Avatar({ author, size = 's40', square = false, showVerified = false, className = '' }) {
  if (!author) return null;
  const initials = author.name.split(' ').slice(-2).map(s => s[0]).join('').toUpperCase();
  const tint = tintMap[author.tint || 'emerald'];
  const sz = sizeMap[size];
  return (
    <span className={`relative inline-grid place-items-center font-semibold flex-none shadow-[inset_0_1px_0_rgba(255,255,255,0.6),0_4px_12px_-4px_rgba(0,60,40,0.20)] ${tint} ${sz} ${square ? 'rounded-lg' : 'rounded-full'} ${className}`}>
      {initials}
      {showVerified && author.verified && (
        <span className="absolute -right-0.5 -bottom-0.5 w-3.5 h-3.5 rounded-full bg-emerald-grad grid place-items-center text-white border-2 border-white/95 dark:border-[#141813] shadow-[0_2px_6px_-1px_rgba(0,170,100,0.5)]">
          <I.Check size={8} sw={2.5} />
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
    <aside className={`sticky top-0 h-screen p-5 flex flex-col gap-1 border-r border-white/40 dark:border-white/8 ${G.glassBar}`}>
      <div className="flex items-center gap-2.5 px-2 pb-5 cursor-pointer">
        <div className="w-8 h-8 rounded-[10px] bg-emerald-grad grid place-items-center text-white font-serif italic font-semibold text-[19px] shadow-glow-emerald">O</div>
        <div className="font-serif text-[19px] font-medium tracking-tight">
          Oecophy<em className="not-italic text-emerald-500">lla</em>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5">
        {items.map(it => {
          const Ic = I[it.icon];
          const isActive = active === it.id;
          return (
            <button key={it.id} onClick={() => onNav(it.id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-2xl text-[14px] font-medium transition-all duration-150
                ${isActive
                  ? 'bg-glass-grad dark:bg-glass-grad-dark text-ink dark:text-white shadow-glass-pill'
                  : 'text-ink-2 dark:text-white/75 hover:bg-white/55 dark:hover:bg-white/8'}`}>
              <Ic size={18}/>
              <span>{it.name}</span>
              {it.count != null && (
                <span className="ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-grad text-white shadow-[0_2px_6px_-1px_rgba(0,170,100,0.5)]">
                  {it.count}
                </span>
              )}
            </button>
          );
        })}
        <div className="mt-4 px-3 pb-1.5 text-[11px] uppercase tracking-[0.08em] text-muted-2 dark:text-white/40 font-semibold">Của bạn</div>
        {[
          { c: 'bg-emerald-500', n: 'AI có trách nhiệm' },
          { c: 'bg-blue-500',    n: 'Kinh tế Việt Nam' },
          { c: 'bg-amber-500',   n: 'Báo chí số' },
        ].map(g => (
          <button key={g.n} onClick={() => onNav('group')}
            className="flex items-center gap-3 px-3 py-2 rounded-2xl text-[13.5px] text-ink-2 dark:text-white/75 hover:bg-white/55 dark:hover:bg-white/8 transition-colors">
            <span className={`w-2.5 h-2.5 rounded-sm ${g.c}`}/>
            {g.n}
          </button>
        ))}
      </nav>

      <div className="mt-auto pt-4 border-t border-ink/8 dark:border-white/10">
        <div className="flex items-center gap-2.5 p-2 rounded-2xl hover:bg-white/55 dark:hover:bg-white/8 cursor-pointer" onClick={() => onNav('profile')}>
          <Avatar author={DATA.AUTHORS[0]} size="s32" />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-semibold truncate">Nguyễn Quỳnh Anh</div>
            <div className="text-[11.5px] text-muted dark:text-white/55">@quynhanh</div>
          </div>
          <I.Settings size={15} className="text-muted"/>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ crumbs, search = true, theme, onTheme, onAdmin, right }) {
  return (
    <header className={`sticky top-0 z-30 h-15 px-7 flex items-center gap-4 border-b border-white/40 dark:border-white/8 ${G.glassBar}`} style={{ height: 60 }}>
      {crumbs && <div className="font-serif text-[18px] tracking-tight">{crumbs}</div>}
      {search && (
        <div className="relative flex-1 max-w-[460px] ml-auto sm:ml-6">
          <I.Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"/>
          <input
            placeholder="Tìm chủ đề, tác giả, hoặc bài viết…"
            className="w-full pl-10 pr-4 py-2 bg-white/55 dark:bg-white/6 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-full text-[13px] outline-none focus:border-ink/40 dark:focus:border-white/30 transition"
          />
        </div>
      )}
      <div className="flex items-center gap-1 ml-auto">
        {right}
        <button className={G.iconBtn} title="Đổi giao diện" onClick={onTheme}>
          {theme === 'dark' ? <I.Sun size={18}/> : <I.Moon size={18}/>}
        </button>
        <button className={`${G.iconBtn} relative`} title="Thông báo">
          <I.Bell size={18}/>
          <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-[#141813]"/>
        </button>
        {onAdmin && (
          <button onClick={onAdmin} className={`${G.btn} ${G.btnGhost} ${G.btnSm} ml-1.5`}>
            <I.Shield size={13}/> Quản trị
          </button>
        )}
      </div>
    </header>
  );
}

function ModBadge({ kind, label }) {
  const map = {
    'verified-src': [G.badgeVerified, 'Shield'],
    'moderated':    [G.badgeModerated, 'Check'],
    'pending':      [G.badgePending, 'Clock'],
    'flagged':      [G.badgeFlagged, 'Flag'],
    'ai':           [G.badgeAi, 'Sparkle'],
  };
  const [cls, ic] = map[kind] || map.moderated;
  const Ic = I[ic];
  return <span className={`${G.badgeBase} ${cls}`}><Ic size={11}/> {label}</span>;
}

function TopicChip({ topicId, ...rest }) {
  const t = DATA.TOPICS.find(x => x.id === topicId);
  if (!t) return null;
  return <span className={G.chip} {...rest}>#{t.name}</span>;
}

function PostCard({ post, onLike, onSave, onOpen, liked, saved, hideRecommend = false }) {
  const a = post.author;
  return (
    <article className={`${G.card} p-6 mb-3.5 transition-all hover:-translate-y-0.5 hover:shadow-glass-lg`}>
      <header className="flex items-center gap-3 mb-3.5">
        <Avatar author={a} size="s40" showVerified />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 font-semibold text-[14px]">
            {a.name}
            {a.verified && <I.Verified size={13} className="text-blue-600 dark:text-blue-400"/>}
          </div>
          <div className="text-[12px] text-muted dark:text-white/55 flex items-center gap-1.5 mt-0.5">
            {a.handle} · <I.Clock size={11}/> {post.time}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <ModBadge kind={post.moderation} label={post.moderationLabel} />
          <button className={G.iconBtn}><I.More size={16}/></button>
        </div>
      </header>

      <h3 onClick={onOpen}
        className="font-serif text-[22px] leading-[1.22] tracking-tight font-medium mb-2 cursor-pointer hover:text-emerald-700 dark:hover:text-emerald-400 transition-colors">
        {post.title}
      </h3>
      <p className="text-[14.5px] leading-[1.55] text-ink-2 dark:text-white/80">{post.summary}</p>

      {post.image && (
        <div className="mt-3.5 w-full aspect-video oc-ph rounded-2xl grid place-items-center font-mono text-[10px] uppercase tracking-wider">
          ẢNH BÌA · 16:9
        </div>
      )}

      {post.link && (
        <div className="mt-3.5 flex items-stretch gap-3.5 border border-white/60 dark:border-white/8 rounded-2xl overflow-hidden bg-white/30 dark:bg-white/3 backdrop-blur-md">
          <div className="oc-ph w-[140px] flex-none aspect-square grid place-items-center font-mono text-[10px] uppercase tracking-wider">LINK</div>
          <div className="p-3.5 flex flex-col gap-1 justify-center">
            <span className={G.eyebrow}><I.ExternalLink size={10} className="inline -mt-0.5 mr-1"/>{post.link.domain}</span>
            <div className="font-serif text-[14px] leading-snug font-medium">{post.link.title}</div>
          </div>
        </div>
      )}

      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {post.tags.map(t => <TopicChip key={t} topicId={t} />)}
        <span className="ml-auto text-[12px] text-muted dark:text-white/55 flex items-center gap-1">
          <I.Eye size={12}/> {post.stats.reads} lượt đọc
        </span>
      </div>

      {!hideRecommend && (
        <div className="mt-3.5 px-3 py-2 rounded-xl flex items-center gap-2 text-[12.5px] text-emerald-700 dark:text-emerald-300 bg-gradient-to-r from-emerald-500/18 to-emerald-300/8 border border-emerald-500/20 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]">
          <I.Sparkle size={14}/> {post.reason}
        </div>
      )}

      <div className="mt-4 pt-3.5 border-t border-ink/8 dark:border-white/10 flex items-center gap-1 flex-wrap">
        <ActionButton active={liked} onClick={onLike}
          icon={liked ? <I.HeartFill size={16}/> : <I.Heart size={16}/>}
          activeClass="text-rose-600 bg-rose-500/12 dark:bg-rose-500/20">
          {post.stats.likes + (liked ? 1 : 0)}
        </ActionButton>
        <ActionButton icon={<I.Comment size={16}/>}>{post.stats.comments}</ActionButton>
        <ActionButton icon={<I.Share size={16}/>}>{post.stats.shares}</ActionButton>
        <ActionButton active={saved} onClick={onSave}
          icon={saved ? <I.BookmarkFill size={16}/> : <I.Bookmark size={16}/>}
          activeClass="text-emerald-600 bg-emerald-500/15">
          {saved ? 'Đã lưu' : 'Lưu'}
        </ActionButton>
        <span className="flex-1"/>
        <ActionButton icon={<I.EyeOff size={16}/>} title="Ẩn bài"/>
        <ActionButton icon={<I.Flag size={16}/>} title="Báo cáo"/>
      </div>
    </article>
  );
}

function ActionButton({ active, onClick, icon, children, activeClass = '', title }) {
  const base = 'inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[13px] font-medium transition-colors';
  const inactive = 'text-muted dark:text-white/55 hover:bg-white/50 dark:hover:bg-white/8 hover:text-ink dark:hover:text-white';
  return (
    <button onClick={onClick} title={title} className={`${base} ${active ? activeClass : inactive}`}>
      {icon}
      {children}
    </button>
  );
}

function Toast({ children, onClose }) {
  useEffectTw(() => { const t = setTimeout(onClose, 2200); return () => clearTimeout(t); }, []);
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-full text-[13px] font-medium text-white bg-[rgba(15,22,20,0.85)] backdrop-blur-2xl border border-white/15 shadow-[0_16px_40px_-8px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.2)] flex items-center gap-2 oc-toast-in">
      <I.Check size={14}/> {children}
    </div>
  );
}

Object.assign(window, { Avatar, Sidebar, Topbar, ModBadge, TopicChip, PostCard, Toast, ActionButton });
