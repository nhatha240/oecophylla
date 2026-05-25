/* Explore + Profile + Notifications — Tailwind */
const GP = window.G;
const IP = window.I;
const DP = window.DATA;

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
    <div className="max-w-[1180px] mx-auto px-8 py-7 pb-20" data-screen-label="06 Explore">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-[28px] mb-7 p-12 border border-white/15 shadow-[0_20px_60px_-16px_rgba(0,60,40,0.4)] backdrop-blur-md
        bg-gradient-to-br from-[rgba(8,32,22,0.88)] to-[rgba(20,60,40,0.78)] text-white">
        <div className="absolute -right-20 -top-20 w-80 h-80 rounded-full bg-emerald-500/20 blur-3xl"/>
        <div className="absolute right-32 -bottom-20 w-52 h-52 rounded-full bg-emerald-300/15 blur-2xl"/>
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/60">Khám phá</span>
        <h1 className="mt-1.5 font-serif text-[38px] leading-[1.1] tracking-[-0.022em] font-medium max-w-[540px]">
          Tin tức, ý tưởng và cộng đồng <em className="not-italic text-emerald-300 italic">phù hợp với bạn</em>
        </h1>
        <p className="mt-3 text-[15px] text-white/70 max-w-[540px] leading-relaxed">
          Tìm kiếm sâu hơn theo chủ đề, tác giả hoặc nhóm. Bộ lọc giúp bạn lọc theo độ tin cậy của nguồn và thời gian xuất bản.
        </p>
        <div className="relative mt-7 max-w-[520px] bg-white/95 rounded-full pl-11 pr-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_8px_24px_-6px_rgba(0,0,0,0.2)] text-ink">
          <IP.Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted"/>
          <input placeholder='Thử "Edge AI", "lãi suất quý 3", "@minhkhoa"…'
            className="w-full bg-transparent text-[15px] outline-none placeholder:text-muted"/>
        </div>
      </section>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-5">
        {filters.map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)}
            className={`${GP.chip} ${filter === f.id ? GP.chipActive : ''}`}>
            {filter === f.id && <IP.Check size={11} sw={2.4}/>}
            {f.name}
          </button>
        ))}
        <button className={`${GP.chip} ${GP.chipOutline} ml-auto`}>
          <IP.Filter size={12}/> Bộ lọc nâng cao
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-7">
        <div>
          <SectionHeader title="Chủ đề đang tăng trưởng" link="Xem tất cả"/>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { name: 'AI tạo sinh', sub: '2.4K bài · 14K tương tác hôm nay', delta: '+34%' },
              { name: 'An toàn thông tin', sub: '1.1K bài · 8K tương tác hôm nay', delta: '+22%' },
              { name: 'Kinh tế số', sub: '842 bài · 5K tương tác hôm nay', delta: '+18%' },
              { name: 'Edge AI', sub: '432 bài · 3K tương tác hôm nay', delta: '+62%' },
            ].map((t, i) => (
              <div key={i} className={`${GP.card} p-4 flex gap-4 items-center cursor-pointer transition-all hover:-translate-y-0.5`}>
                <div className="oc-ph w-[88px] h-[88px] flex-none rounded-2xl grid place-items-center font-mono text-[10px] uppercase">CHỦ ĐỀ</div>
                <div className="flex-1 min-w-0">
                  <h5 className="font-serif text-[17px] tracking-tight font-medium mb-1.5">{t.name}</h5>
                  <div className="text-[12px] text-muted dark:text-white/55">{t.sub}</div>
                  <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                    <IP.TrendUp size={11}/> {t.delta} so với tuần trước
                  </span>
                </div>
              </div>
            ))}
          </div>

          <SectionHeader title="Bài viết nổi bật cho bạn" link="Đổi mới"/>
          {DP.POSTS.slice(0, 3).map(p => (
            <PostCard key={p.id} post={p} onOpen={() => onOpenPost(p)} onLike={() => {}} onSave={() => {}}/>
          ))}
        </div>

        <aside className="flex flex-col gap-4">
          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium flex items-center gap-2"><IP.Sparkle size={16} className="text-emerald-500"/> Chủ đề dành cho bạn</h4>
            <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3">Dựa trên 30 ngày đọc gần đây.</p>
            <div className="flex flex-wrap gap-1.5">
              {['AI có trách nhiệm', 'Edge AI', 'Khoa học dữ liệu', 'Báo chí số', 'Năng lượng tái tạo', 'Khởi nghiệp Việt', 'Edtech', 'Bảo mật'].map(t => (
                <span key={t} className={`${GP.chip} ${GP.chipActive}`}>+ {t}</span>
              ))}
            </div>
          </div>

          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium flex items-center gap-2"><IP.Shield size={16} className="text-emerald-500"/> Nguồn tin đáng tin cậy</h4>
            {DP.AUTHORS.filter(a => a.verified).slice(0, 4).map(a => (
              <div key={a.id} className="flex items-center gap-2.5 py-2.5 border-t border-ink/8 dark:border-white/10 first:border-t-0">
                <Avatar author={a} size="s40" showVerified/>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold flex items-center gap-1">{a.name} <IP.Verified size={12} className="text-blue-600"/></div>
                  <div className="text-[11.5px] text-muted dark:text-white/55 truncate">{a.bio}</div>
                </div>
              </div>
            ))}
          </div>

          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium flex items-center gap-2 mb-3.5"><IP.Group size={16} className="text-emerald-500"/> Nhóm gợi ý</h4>
            {[
              { name: 'AI có trách nhiệm Vietnam', m: '4.2K thành viên', tone: 'emerald' },
              { name: 'Báo chí Số', m: '2.8K thành viên', tone: 'azure' },
              { name: 'Edtech Builders', m: '1.6K thành viên', tone: 'amber' },
            ].map((g, i) => {
              const dot = { emerald: 'from-emerald-400 to-emerald-700', azure: 'from-blue-400 to-blue-700', amber: 'from-amber-400 to-amber-700' }[g.tone];
              return (
                <div key={i} className={`flex items-center gap-2.5 py-2.5 ${i ? 'border-t border-ink/8 dark:border-white/10' : ''}`}>
                  <span className={`w-10 h-10 rounded-lg bg-gradient-to-br ${dot} text-white grid place-items-center shadow-glass-inner`}><IP.Group size={18}/></span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold">{g.name}</div>
                    <div className="text-[11.5px] text-muted dark:text-white/55">{g.m}</div>
                  </div>
                  <button className={`${GP.btn} ${GP.btnGhost} ${GP.btnSm}`}>Tham gia</button>
                </div>
              );
            })}
          </div>
        </aside>
      </div>
    </div>
  );
}

function SectionHeader({ title, link }) {
  return (
    <div className="flex items-center justify-between mt-8 mb-3.5">
      <h3 className="font-serif text-[22px] font-medium tracking-tight">{title}</h3>
      <a className="text-[13px] font-semibold text-emerald-700 dark:text-emerald-300 inline-flex items-center gap-1 cursor-pointer">
        {link} <IP.ArrowRight size={12}/>
      </a>
    </div>
  );
}

/* ===== Profile ===== */
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
  const me = DP.AUTHORS[0];

  return (
    <div className="max-w-[980px] mx-auto px-8 pb-20" data-screen-label="07 Profile">
      <div className="h-44 rounded-b-[28px] relative overflow-hidden bg-gradient-to-br from-[#00C480] via-[#008A57] to-[#006840] shadow-[0_16px_40px_-10px_rgba(0,170,100,0.4)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_50%,rgba(255,255,255,0.2),transparent_50%)]"/>
        <div className="absolute inset-0 opacity-30" style={{ background: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 12px)' }}/>
      </div>

      <div className="flex flex-col sm:flex-row items-end gap-5 -mt-16 px-6 pb-6">
        <Avatar author={me} size="s120" showVerified className="border-4 border-white/95 dark:border-[#141813] shadow-[0_12px_32px_-8px_rgba(0,60,40,0.3)]"/>
        <div className="flex-1 pb-2">
          <h2 className="font-serif text-[30px] tracking-tight font-medium flex items-center gap-2">
            {me.name}
            <IP.Verified size={18} className="text-blue-600 dark:text-blue-400"/>
          </h2>
          <div className="text-[14px] text-muted dark:text-white/60">{me.handle} · Hà Nội</div>
          <p className="mt-2.5 max-w-[580px] leading-relaxed text-ink-2 dark:text-white/80">
            Biên tập tin công nghệ, quan tâm AI có trách nhiệm và báo chí số tại Việt Nam.
            Viết về cách công nghệ thay đổi cách chúng ta đọc tin.
          </p>
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            <span className={`${GP.chip} ${GP.chipActive}`}>AI</span>
            <span className={`${GP.chip} ${GP.chipActive}`}>Báo chí số</span>
            <span className={`${GP.chip} ${GP.chipActive}`}>Edu-tech</span>
            <span className={`${GP.chip} ${GP.chipOutline}`}>+ 4</span>
          </div>
          <div className="flex gap-6 mt-3 text-[13px]">
            <div><b className="font-semibold">1.842</b> <span className="text-muted dark:text-white/55">người theo dõi</span></div>
            <div><b className="font-semibold">283</b> <span className="text-muted dark:text-white/55">đang theo dõi</span></div>
            <div><b className="font-semibold">42</b> <span className="text-muted dark:text-white/55">bài viết</span></div>
            <div><b className="font-semibold">7</b> <span className="text-muted dark:text-white/55">nhóm</span></div>
          </div>
        </div>
        <div className="flex gap-2 pb-2">
          <button className={`${GP.btn} ${GP.btnGhost}`}><IP.Share size={14}/> Chia sẻ</button>
          <button className={`${GP.btn} ${GP.btnInk}`}><IP.Edit size={14}/> Chỉnh sửa hồ sơ</button>
        </div>
      </div>

      <div className={GP.tabs + ' flex-wrap'}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`${GP.tab} ${tab === t.id ? GP.tabActive : ''}`}>
            {t.name}
            {t.count != null && <span className={`text-[10.5px] px-1.5 py-0.5 rounded-full ${tab === t.id ? 'bg-emerald-500/15 text-emerald-700' : 'bg-ink/8 dark:bg-white/10 text-muted'}`}>{t.count}</span>}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_290px] gap-7 mt-7">
        <div>
          {tab === 'posts' && DP.POSTS.slice(0, 2).map(p => (
            <PostCard key={p.id} post={{...p, author: me}} onLike={() => {}} onSave={() => {}} onOpen={() => {}} hideRecommend/>
          ))}
          {tab === 'comments' && (
            <div className={`${GP.card} p-5`}>
              {DP.POSTS.slice(0, 3).map((p, i) => (
                <div key={p.id} className={`py-4 ${i ? 'border-t border-ink/8 dark:border-white/10' : ''}`}>
                  <div className="text-[12px] text-muted dark:text-white/55 mb-1">Bình luận trong: <b className="text-ink dark:text-white">{p.title}</b></div>
                  <div className="text-[14px] leading-relaxed">
                    {p.id === 'p1' ? 'Cảm ơn nhóm đã làm khảo sát này. Có công bố dataset không ạ?' :
                     p.id === 'p2' ? 'Quan điểm phòng thủ là hợp lý trong bối cảnh hiện tại, nhưng cần xem thêm tín hiệu từ FDI…' :
                     'Bài hay, mong đọc thêm các góc nhìn từ địa phương khác nữa.'}
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'saved' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {DP.POSTS.slice(0, 4).map(p => (
                <div key={p.id} className={`${GP.card} p-5 cursor-pointer`}>
                  <div className={GP.eyebrow + ' mb-1.5'}>{DP.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
                  <div className="font-serif text-[17px] leading-snug tracking-tight font-medium mb-2">{p.title}</div>
                  <div className="text-[12px] text-muted dark:text-white/55">{p.author.name} · {p.time}</div>
                </div>
              ))}
            </div>
          )}
          {tab === 'groups' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {['AI có trách nhiệm Vietnam', 'Báo chí Số', 'Edtech Builders', 'Khoa học mở'].map((g, i) => (
                <div key={i} className={`${GP.card} p-5 flex gap-3 items-center`}>
                  <span className="w-14 h-14 rounded-2xl bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 grid place-items-center"><IP.Group size={22}/></span>
                  <div>
                    <div className="font-semibold">{g}</div>
                    <div className="text-[12px] text-muted dark:text-white/55">{[1.4, 2.8, 1.6, 0.9][i]}K thành viên · Bạn là quản trị</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'activity' && (
            <div className={`${GP.card} p-5`}>
              {[
                { ic: 'HeartFill', tone: 'rose', txt: <>Bạn đã thích bài <b>"Quy định mới về dán nhãn nội dung do AI tạo ra"</b></>, t: '2 giờ trước' },
                { ic: 'Bookmark', tone: 'emerald', txt: <>Bạn đã lưu bài <b>"Tự host một mô hình 8B trên Mac Mini M4"</b></>, t: '6 giờ' },
                { ic: 'Comment', tone: 'azure', txt: <>Bạn đã bình luận trong <b>"Vì sao mô hình ngôn ngữ Việt Nam vẫn lệch"</b></>, t: 'Hôm qua' },
                { ic: 'User', tone: 'violet', txt: <>Bạn đã theo dõi <b>Bùi Khánh Linh</b></>, t: '2 ngày' },
              ].map((row, i) => {
                const Ic = IP[row.ic];
                const toneCls = { rose: 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300',
                  emerald: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
                  azure: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
                  violet: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300' };
                return (
                  <div key={i} className={`flex gap-3 py-3.5 ${i ? 'border-t border-ink/8 dark:border-white/10' : ''}`}>
                    <span className={`w-8 h-8 rounded-full grid place-items-center flex-none ${toneCls[row.tone]}`}><Ic size={14}/></span>
                    <div className="flex-1">
                      <div className="text-[13.5px]">{row.txt}</div>
                      <div className="text-[11.5px] text-muted dark:text-white/55 mt-0.5">{row.t}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <aside className="flex flex-col gap-3.5">
          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium">Hồ sơ sở thích</h4>
            <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3.5 leading-relaxed">
              Các chủ đề Oecophylla nhận diện từ hành vi đọc của bạn. Bạn có thể chỉnh trực tiếp.
            </p>
            <div className="flex flex-col gap-3">
              {DP.TASTE.map(t => (
                <div key={t.topic}>
                  <div className="flex justify-between text-[12px] mb-1">
                    <span>{t.topic}</span><span className="text-muted dark:text-white/55">{t.pct}%</span>
                  </div>
                  <div className="h-1 bg-ink/8 dark:bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-[#00C480] to-[#008A57] rounded-full" style={{ width: t.pct + '%' }}/>
                  </div>
                </div>
              ))}
            </div>
            <button className={`${GP.btn} ${GP.btnGhost} ${GP.btnSm} w-full mt-3.5`}>
              <IP.Edit size={12}/> Chỉnh sở thích
            </button>
          </div>

          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium">Kiểm soát cá nhân hóa</h4>
            <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3 leading-relaxed">Bạn quyết định mức độ thuật toán định hình bảng tin.</p>
            <ToggleRow label="Bật cá nhân hóa" desc="Tắt để chỉ thấy bài theo thời gian." on={personalization} onToggle={() => setPersonalization(!personalization)}/>
            <ToggleRow label="Hiển thị nội dung nhạy cảm" desc="Đã được kiểm duyệt và gắn nhãn." on={showSensitive} onToggle={() => setShowSensitive(!showSensitive)}/>
            <ToggleRow label="Trộn chủ đề ngoài sở thích" desc="Giúp tránh bong bóng thông tin." on={activityMix} onToggle={() => setActivityMix(!activityMix)}/>
          </div>

          <div className={`${GP.card} p-5`}>
            <h4 className="font-serif text-[16px] font-medium">Chủ đề đang ẩn</h4>
            <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3">Bạn đã chọn không xem các chủ đề này.</p>
            <div className="flex flex-wrap gap-1.5">
              <span className={`${GP.chip} ${GP.chipOutline}`}>Bóng đá <IP.X size={10}/></span>
              <span className={`${GP.chip} ${GP.chipOutline}`}>Giải trí <IP.X size={10}/></span>
              <button className={`${GP.chip} ${GP.chipOutline}`}><IP.Plus size={11}/> Thêm</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function ToggleRow({ label, desc, on, onToggle }) {
  return (
    <div className="flex items-center justify-between gap-3.5 py-3 border-t border-ink/8 dark:border-white/10 first:border-t-0">
      <div>
        <div className="text-[13px] font-medium">{label}</div>
        <div className="text-[11.5px] text-muted dark:text-white/55 mt-0.5 leading-snug">{desc}</div>
      </div>
      <button onClick={onToggle} aria-label="toggle"
        className={`relative w-9 h-5 rounded-full transition-colors shadow-[inset_0_1px_2px_rgba(0,0,0,0.1)]
          ${on ? 'bg-gradient-to-br from-[#00C480] to-[#008A57] shadow-[inset_0_1px_2px_rgba(0,0,0,0.1),0_0_12px_rgba(0,200,130,0.4)]' : 'bg-ink/15 dark:bg-white/15'}`}>
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-[0_1px_3px_rgba(0,0,0,0.25),0_2px_6px_rgba(0,0,0,0.1)] ${on ? 'translate-x-3.5' : ''}`}/>
      </button>
    </div>
  );
}

/* ===== Notifications ===== */
function Notifications() {
  const [cat, setCat] = React.useState('all');
  const [readSet, setReadSet] = React.useState(new Set());
  const cats = [
    { id: 'all', name: 'Tất cả' },
    { id: 'Tương tác', name: 'Tương tác' },
    { id: 'Kiểm duyệt', name: 'Kiểm duyệt' },
    { id: 'Gợi ý', name: 'Gợi ý' },
  ];
  const list = DP.NOTIFICATIONS.filter(n => cat === 'all' || n.cat === cat);
  const tone = {
    rose:    'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300',
    emerald: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
    azure:   'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
    violet:  'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
    amber:   'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  };
  return (
    <div className="max-w-[760px] mx-auto px-8 py-6 pb-20" data-screen-label="08 Notifications">
      <div className="flex items-baseline justify-between mb-3.5">
        <h2 className="font-serif text-[28px] font-medium tracking-tight">Thông báo</h2>
        <button onClick={() => setReadSet(new Set(list.map(n => n.id)))} className={`${GP.btn} ${GP.btnGhost} ${GP.btnSm}`}>
          <IP.Check size={12}/> Đánh dấu tất cả đã đọc
        </button>
      </div>

      <div className={`${GP.tabs} mb-5`}>
        {cats.map(c => (
          <button key={c.id} onClick={() => setCat(c.id)} className={`${GP.tab} ${cat === c.id ? GP.tabActive : ''}`}>{c.name}</button>
        ))}
      </div>

      <div className={`${GP.card} overflow-hidden`}>
        {list.map((n, i) => {
          const Ic = IP[n.icon];
          const isUnread = n.unread && !readSet.has(n.id);
          return (
            <div key={n.id} onClick={() => setReadSet(new Set([...readSet, n.id]))}
              className={`relative flex gap-3.5 px-5 py-4 items-start cursor-pointer transition-colors
                ${i ? 'border-t border-ink/6 dark:border-white/6' : ''}
                ${isUnread ? 'bg-gradient-to-r from-emerald-500/14 to-emerald-500/2' : 'hover:bg-white/40 dark:hover:bg-white/4'}`}>
              {isUnread && <span className="absolute left-2 top-5 w-1.5 h-1.5 rounded-full bg-emerald-500"/>}
              <span className={`w-9 h-9 rounded-full grid place-items-center flex-none backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.5)] ${tone[n.tone]}`}>
                <Ic size={16}/>
              </span>
              <div className="flex-1">
                <div className="text-[14px] leading-snug">{n.msg}</div>
                <div className="text-[11px] text-muted dark:text-white/55 mt-1 flex items-center gap-2">
                  <span>{n.time}</span><span>·</span><span>{n.cat}</span>
                </div>
              </div>
              {n.who && <Avatar author={n.who} size="s32"/>}
            </div>
          );
        })}
        {list.length === 0 && (
          <div className="px-6 py-16 text-center text-muted dark:text-white/55">Không có thông báo nào trong mục này.</div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { Explore, Profile, Notifications });
