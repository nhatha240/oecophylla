/* Mobile preview — Tailwind */
const GM = window.G;
const IM = window.I;
const DM = window.DATA;

function MobilePreview({ onBack }) {
  return (
    <div className="max-w-[1100px] mx-auto px-8 pt-10 pb-20" data-screen-label="10 Mobile">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-serif text-[28px] font-medium tracking-tight">Xem trên di động</h2>
          <div className="text-[13px] text-muted dark:text-white/60 mt-1">
            Bottom navigation 5 mục. Composer mở dạng modal toàn màn hình.
          </div>
        </div>
        <button onClick={onBack} className={`${GM.btn} ${GM.btnGhost} ${GM.btnSm}`}><IM.ArrowLeft size={13}/> Quay lại desktop</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 justify-items-center mt-6">
        <div>
          <div className={`${GM.eyebrow} text-center mb-3.5`}>Home feed</div>
          <PhoneFrame><MobileHomeFeed/><BottomNav active="home"/></PhoneFrame>
        </div>
        <div>
          <div className={`${GM.eyebrow} text-center mb-3.5`}>Trang chi tiết bài viết</div>
          <PhoneFrame><MobileArticle/><BottomNav active="home"/></PhoneFrame>
        </div>
      </div>
    </div>
  );
}

function PhoneFrame({ children }) {
  return (
    <div className="w-[390px] h-[760px] rounded-[40px] border border-white/60 dark:border-white/10 bg-white/45 dark:bg-glass-dark-base backdrop-blur-3xl backdrop-saturate-150 shadow-[0_32px_80px_-16px_rgba(0,60,40,0.30),inset_0_1px_0_rgba(255,255,255,0.9)] overflow-hidden flex flex-col">
      <div className="h-9 px-5 flex items-center justify-between text-[12px] font-semibold">
        <span>9:41</span>
        <div className="flex gap-1 items-center text-[11px]">
          <span>●●●●</span><span className="ml-1.5">5G</span><span className="ml-1.5">▮▮▮▯</span>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

function BottomNav({ active }) {
  const items = [
    { id: 'home', name: 'Trang chủ', ic: 'Home' },
    { id: 'expl', name: 'Khám phá',  ic: 'Compass' },
    { id: 'post', name: '',          ic: 'Plus' },
    { id: 'notif',name: 'Thông báo', ic: 'Bell' },
    { id: 'me',   name: 'Hồ sơ',     ic: 'User' },
  ];
  return (
    <div className="grid grid-cols-5 pt-1.5 pb-3.5 border-t border-ink/6 dark:border-white/8 bg-white/70 dark:bg-glass-dark-base backdrop-blur-2xl">
      {items.map(n => {
        const Ic = IM[n.ic];
        if (n.id === 'post') {
          return (
            <button key={n.id} className="flex items-center justify-center">
              <span className="w-9 h-9 rounded-xl bg-emerald-grad text-white grid place-items-center shadow-glow-emerald">
                <Ic size={16}/>
              </span>
            </button>
          );
        }
        const isActive = active === n.id;
        return (
          <button key={n.id} className={`flex flex-col items-center gap-0.5 p-1.5 text-[10px] font-medium ${isActive ? 'text-emerald-600' : 'text-muted'}`}>
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
    <div className="h-full overflow-auto">
      <div className={`sticky top-0 z-10 px-4 py-3 flex items-center gap-2.5 border-b border-ink/6 dark:border-white/8 ${GM.glassBar}`}>
        <div className="w-6 h-6 rounded-lg bg-emerald-grad grid place-items-center text-white font-serif italic font-semibold text-[14px] shadow-glow-emerald">O</div>
        <div className="font-serif text-[17px] tracking-tight">Oecophy<em className="not-italic text-emerald-500">lla</em></div>
        <button className="w-8 h-8 grid place-items-center rounded-lg hover:bg-white/55 ml-auto"><IM.Search size={16}/></button>
        <button className="w-8 h-8 grid place-items-center rounded-lg hover:bg-white/55 relative">
          <IM.Bell size={16}/>
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 ring-2 ring-white"/>
        </button>
      </div>

      <div className="flex gap-1 px-3 py-2 overflow-x-auto border-b border-ink/6 dark:border-white/8">
        {['Dành cho bạn', 'Đang theo dõi', 'Tin mới', 'Xu hướng', 'Đã lưu'].map((t, i) => (
          <button key={i} className={`px-3 py-1.5 text-[12px] font-semibold rounded-full whitespace-nowrap
            ${i === 0 ? 'bg-glass-grad text-ink shadow-glass-pill' : 'bg-white/40 text-ink-2 dark:bg-white/8 dark:text-white/75'}`}>
            {t}
          </button>
        ))}
      </div>

      <div className="p-3.5 flex flex-col gap-3">
        {DM.POSTS.slice(0, 3).map(p => (
          <article key={p.id} className={`${GM.card} p-4`}>
            <div className="flex items-center gap-2.5 mb-2.5">
              <Avatar author={p.author} size="s32" showVerified/>
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-[13px] flex items-center gap-1">
                  {p.author.name}
                  {p.author.verified && <IM.Verified size={11} className="text-blue-600"/>}
                </div>
                <div className="text-[11px] text-muted dark:text-white/55">{p.time} · {DM.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
              </div>
              <ModBadge kind={p.moderation} label={p.moderationLabel}/>
            </div>
            <div className="font-serif text-[16px] tracking-tight font-medium leading-snug mb-1.5">{p.title}</div>
            <div className="text-[12.5px] text-ink-2 dark:text-white/80 leading-snug mb-2.5 line-clamp-2">{p.summary}</div>
            {p.image && <div className="oc-ph aspect-video rounded-xl mb-2.5 grid place-items-center font-mono text-[10px] uppercase">ẢNH</div>}
            <div className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[11px] mb-2.5">
              <IM.Sparkle size={11}/> {p.reason}
            </div>
            <div className="flex gap-1 pt-2.5 border-t border-ink/8 dark:border-white/10">
              <button className="px-2 py-1 text-[12px] text-muted flex items-center gap-1"><IM.Heart size={14}/> {p.stats.likes}</button>
              <button className="px-2 py-1 text-[12px] text-muted flex items-center gap-1"><IM.Comment size={14}/> {p.stats.comments}</button>
              <button className="px-2 py-1 text-[12px] text-muted"><IM.Share size={14}/></button>
              <span className="flex-1"/>
              <button className="px-2 py-1 text-[12px] text-muted"><IM.Bookmark size={14}/></button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function MobileArticle() {
  const p = DM.POSTS[0];
  return (
    <div className="h-full overflow-auto">
      <div className={`sticky top-0 z-10 px-4 py-3 flex items-center gap-2.5 border-b border-ink/6 dark:border-white/8 ${GM.glassBar}`}>
        <button className="w-8 h-8 grid place-items-center rounded-lg hover:bg-white/55"><IM.ArrowLeft size={16}/></button>
        <div className="flex-1 text-center font-semibold text-[13px]">Bài viết</div>
        <button className="w-8 h-8 grid place-items-center rounded-lg hover:bg-white/55"><IM.Bookmark size={16}/></button>
        <button className="w-8 h-8 grid place-items-center rounded-lg hover:bg-white/55"><IM.Share size={16}/></button>
      </div>
      <div className="px-5 py-5 pb-10">
        <div className="flex flex-wrap gap-1.5 mb-3">
          <ModBadge kind="verified-src" label="Nguồn đáng tin cậy"/>
          <span className="text-[12px] text-muted"><IM.Clock size={11} className="inline -mt-0.5"/> 8 phút đọc</span>
        </div>
        <h1 className="font-serif text-[24px] leading-[1.15] tracking-[-0.025em] font-medium mb-2.5">{p.title}</h1>
        <p className="font-serif italic text-[14px] text-muted leading-snug mb-4">{p.summary}</p>
        <div className="flex items-center gap-2.5 py-3 border-y border-ink/8 dark:border-white/10">
          <Avatar author={p.author} size="s40" showVerified/>
          <div className="flex-1">
            <div className="font-semibold text-[13px]">{p.author.name}</div>
            <div className="text-[11.5px] text-muted">{p.author.handle} · {p.time}</div>
          </div>
          <button className={`${GM.btn} ${GM.btnEmerald} ${GM.btnSm}`}>Theo dõi</button>
        </div>
        <div className="oc-ph aspect-video rounded-xl my-4 grid place-items-center font-mono text-[10px] uppercase">ẢNH MINH HỌA</div>
        <p className="font-serif text-[15px] leading-[1.6] text-ink-2 dark:text-white/85">
          Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ
          lớn phổ biến với một bộ dữ liệu kiểm thử riêng…
        </p>
        <div className="mt-4 p-4 rounded-3xl bg-gradient-to-br from-emerald-500/16 to-blue-400/12 border border-white/60 dark:border-white/10 backdrop-blur-2xl shadow-glass-inner">
          <h4 className="font-serif text-[14px] font-medium text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5 mb-1.5">
            <IM.Sparkle size={12}/> Vì sao bạn thấy bài này?
          </h4>
          <p className="text-[12.5px] text-ink-2 dark:text-white/80">
            Bạn đã đọc nhiều bài về AI có trách nhiệm. Nguồn được xác minh, độ tin cậy cao.
          </p>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MobilePreview });
