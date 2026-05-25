/* Admin (Overview, Moderation, Recommendations) — Tailwind */
const GA = window.G;
const IA = window.I;
const DA = window.DATA;
const { AreaChart, Donut, BarsHorizontal } = window;

function AdminShell({ children, page, onNav, onExit }) {
  const items = [
    { sec: 'Bảng điều khiển' },
    { id: 'overview', name: 'Tổng quan',         icon: 'ChartBar' },
    { id: 'posts',    name: 'Quản lý bài viết',  icon: 'FileText' },
    { id: 'flagged',  name: 'Bài bị gắn cờ',     icon: 'Flag', count: 14 },
    { id: 'mod',      name: 'Kiểm duyệt nội dung', icon: 'Shield', count: 28 },
    { sec: 'Cộng đồng' },
    { id: 'users',    name: 'Quản lý người dùng', icon: 'Users' },
    { id: 'groups',   name: 'Quản lý nhóm',       icon: 'Group' },
    { id: 'topics',   name: 'Chủ đề / Metadata',  icon: 'Tag' },
    { id: 'reports',  name: 'Báo cáo người dùng', icon: 'AlertTriangle', count: 6 },
    { sec: 'Hệ thống' },
    { id: 'rec',      name: 'Hiệu quả đề xuất',   icon: 'Activity' },
    { id: 'logs',     name: 'Nhật ký hệ thống',   icon: 'Database' },
  ];
  return (
    <div className="grid grid-cols-[232px_1fr] min-h-screen" data-screen-label="09 Admin">
      <aside className="sticky top-0 h-screen p-5 flex flex-col gap-1 overflow-y-auto text-white border-r border-white/10
        bg-[rgba(8,14,11,0.78)] backdrop-blur-3xl backdrop-saturate-150 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]">
        <div className="flex items-center gap-2.5 px-2 pb-3.5 cursor-pointer" onClick={onExit}>
          <div className="w-8 h-8 rounded-[10px] bg-emerald-grad grid place-items-center text-white font-serif italic font-semibold text-[19px] shadow-glow-emerald">O</div>
          <div className="font-serif text-[19px] tracking-tight">Oecophy<em className="not-italic text-emerald-400">lla</em></div>
        </div>
        <div className="flex items-center gap-1.5 px-2 pb-3.5 text-[11px] uppercase tracking-[0.08em] text-white/50 font-semibold">
          <IA.Shield size={12}/> Khu vực Quản trị
        </div>
        <nav className="flex flex-col gap-0.5">
          {items.map((it, i) => {
            if (it.sec) return <div key={i} className="mt-4 px-3 pb-1.5 text-[11px] uppercase tracking-[0.08em] text-white/40 font-semibold">{it.sec}</div>;
            const Ic = IA[it.icon];
            const isActive = page === it.id;
            return (
              <button key={it.id} onClick={() => onNav(it.id)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-2xl text-[13.5px] font-medium transition-all
                  ${isActive
                    ? 'bg-glass-grad-dark text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_6px_16px_-6px_rgba(0,0,0,0.4)]'
                    : 'text-white/78 hover:bg-white/8 hover:text-white'}`}>
                <Ic size={16} className={isActive ? 'text-emerald-400' : ''}/>
                <span>{it.name}</span>
                {it.count != null && <span className="ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-500 text-white">{it.count}</span>}
              </button>
            );
          })}
        </nav>
        <div className="mt-auto pt-4 border-t border-white/10">
          <button onClick={onExit} className="flex items-center gap-3 px-3 py-2.5 rounded-2xl text-[13.5px] font-medium text-white/78 hover:bg-white/8 hover:text-white w-full text-left">
            <IA.ArrowLeft size={16}/> Trở về Oecophylla
          </button>
          <div className="flex items-center gap-2.5 p-2 rounded-2xl mt-1">
            <Avatar author={DA.AUTHORS[5]} size="s32"/>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold text-white">Bùi Khánh Linh</div>
              <div className="text-[11.5px] text-white/45">Senior Moderator</div>
            </div>
          </div>
        </div>
      </aside>
      <main className="p-7 pb-20 max-w-[1400px]">{children}</main>
    </div>
  );
}

function AdminH({ title, sub, right }) {
  return (
    <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h2 className="font-serif text-[28px] font-medium tracking-tight">{title}</h2>
        <div className="text-[13px] text-muted dark:text-white/60 mt-1">{sub}</div>
      </div>
      <div className="flex gap-2 items-center flex-wrap">{right}</div>
    </div>
  );
}

const DateRange = ({ icon, children }) => (
  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-white/55 dark:bg-white/6 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-2xl text-[13px] cursor-pointer">
    {icon} {children} <IA.Chevron size={11}/>
  </div>
);

function AdminOverview() {
  const kpis = [
    { lab: 'Tổng người dùng', val: '184.2K', delta: '+2.4%' },
    { lab: 'Bài viết hôm nay', val: '3.812', delta: '+12%' },
    { lab: 'Bài chờ duyệt', val: '142', delta: '-8%', invert: true },
    { lab: 'Báo cáo vi phạm', val: '38', delta: '+5', neg: true },
    { lab: 'Tỷ lệ tương tác', val: '6.8%', delta: '+0.4pp' },
    { lab: 'Tỷ lệ bài bị ẩn', val: '1.2%', delta: '-0.1pp', invert: true },
  ];
  const series = [42, 58, 51, 64, 72, 68, 81, 75, 92, 88, 96, 110, 102, 121];
  const compare = [38, 50, 47, 55, 60, 58, 64, 62, 71, 68, 70, 78, 75, 88];

  return (
    <>
      <AdminH title="Tổng quan" sub="Sức khỏe của Oecophylla trong 7 ngày qua. Cập nhật lần cuối 3 phút trước."
        right={<>
          <DateRange icon={<IA.Clock size={13}/>}>7 ngày qua</DateRange>
          <button className={`${GA.btn} ${GA.btnGhost} ${GA.btnSm}`}><IA.Refresh size={13}/> Làm mới</button>
          <button className={`${GA.btn} ${GA.btnInk} ${GA.btnSm}`}><IA.FileText size={13}/> Xuất báo cáo</button>
        </>}/>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3.5 mb-4">
        {kpis.map((k, i) => {
          const good = k.neg ? false : !k.invert;
          return (
            <div key={i} className={`${GA.card} p-4 px-4.5`}>
              <div className="text-[12px] text-muted dark:text-white/60 mb-2">{k.lab}</div>
              <div className="font-serif text-[26px] tracking-tight font-medium leading-none">{k.val}</div>
              <div className={`mt-2.5 inline-flex items-center gap-1 text-[11.5px] font-semibold ${good ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                <IA.ArrowUp size={11} style={{ transform: k.delta.startsWith('-') ? 'rotate(180deg)' : '' }}/> {k.delta} so với tuần trước
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-4">
        <div className={`${GA.card} p-6`}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h4 className="font-serif text-[17px] font-medium">Xu hướng bài viết theo ngày</h4>
              <div className="text-[12px] text-muted dark:text-white/60 mt-1">Tổng bài đăng và bài được duyệt qua kiểm duyệt tự động.</div>
            </div>
            <div className="flex gap-3.5 text-[12px] text-muted dark:text-white/60 flex-wrap">
              <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-sm bg-emerald-500 inline-block"/> Tổng bài</span>
              <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-sm bg-muted-2 inline-block"/> Tuần trước</span>
            </div>
          </div>
          <AreaChart data={series} secondary={compare} height={220}/>
          <div className="flex justify-between mt-2 text-[11px] text-muted dark:text-white/55">
            <span>17/05</span><span>19/05</span><span>21/05</span><span>23/05</span><span>Hôm nay</span>
          </div>
        </div>

        <div className={`${GA.card} p-6`}>
          <h4 className="font-serif text-[17px] font-medium mb-1">Phân bố chủ đề</h4>
          <div className="text-[12px] text-muted dark:text-white/60 mb-4">12.4K bài hôm nay</div>
          <div className="flex items-center gap-4 flex-wrap">
            <Donut size={150} hole={48} label={{ value: '12.4K', sub: 'bài hôm nay' }} slices={[
              { value: 32, color: 'var(--emerald-500, #00A66B)' },
              { value: 22, color: '#2E6FB5' },
              { value: 18, color: '#B58514' },
              { value: 14, color: '#5C45A6' },
              { value: 8,  color: '#C0432A' },
              { value: 6,  color: '#8C948F' },
            ]}/>
            <div className="flex-1 min-w-[140px] flex flex-col gap-1.5 text-[12px]">
              {[['Công nghệ', 32, '#00A66B'], ['Kinh tế', 22, '#2E6FB5'], ['Đời sống', 18, '#B58514'],
                ['AI', 14, '#5C45A6'], ['Xã hội', 8, '#C0432A'], ['Khác', 6, '#8C948F']].map(([n, v, c]) => (
                <div key={n} className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-2"><i className="w-2 h-2 rounded-sm inline-block" style={{ background: c }}/> {n}</span>
                  <b className="font-semibold">{v}%</b>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-4 mt-4">
        <div className={`${GA.card} p-6`}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h4 className="font-serif text-[17px] font-medium">Chất lượng đề xuất</h4>
              <div className="text-[12px] text-muted dark:text-white/60 mt-1">So sánh hiệu quả các nguồn đề xuất.</div>
            </div>
            <a className="text-[13px] font-semibold text-emerald-700 dark:text-emerald-400 cursor-pointer">Xem chi tiết →</a>
          </div>
          <BarsHorizontal max={8} items={[
            { label: 'CTR feed', value: 6.8, display: '6.8%' },
            { label: 'Tỷ lệ lưu bài', value: 4.2, display: '4.2%', color: '#2E6FB5' },
            { label: 'Tỷ lệ ẩn bài', value: 1.2, display: '1.2%', color: '#C0432A' },
            { label: 'Thời gian đọc TB', value: 4.7, display: '128 giây', color: '#B58514' },
          ]}/>
        </div>

        <div className={`${GA.card} p-6`}>
          <h4 className="font-serif text-[17px] font-medium mb-4">Nội dung cần xử lý gấp</h4>
          <div className="flex flex-col gap-2.5">
            {[
              { lead: 'Bài về vacxin COVID có dấu hiệu sai lệch', tag: 'flagged', meta: '12 báo cáo · Rủi ro CAO' },
              { lead: 'Tài khoản giả mạo @vtcnews_real', tag: 'flagged', meta: '8 báo cáo · Rủi ro CAO' },
              { lead: 'Bình luận quấy rối trong nhóm Khoa học mở', tag: 'pending', meta: '3 báo cáo · Rủi ro VỪA' },
              { lead: 'Spam quảng cáo crypto lặp lại', tag: 'flagged', meta: '4 báo cáo · Rủi ro VỪA' },
            ].map((r, i) => (
              <div key={i} className="flex items-center gap-2.5 p-2.5 rounded-2xl bg-white/35 dark:bg-white/4 backdrop-blur-md border border-white/50 dark:border-white/8">
                <ModBadge kind={r.tag} label=""/>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium truncate">{r.lead}</div>
                  <div className="text-[11.5px] text-muted dark:text-white/55">{r.meta}</div>
                </div>
                <button className={`${GA.btn} ${GA.btnInk} ${GA.btnSm}`}>Xem</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function AdminModeration() {
  const items = [
    { id: 1, lead: 'Bài viết cho rằng vacxin COVID gây tổn thương trí nhớ',
      author: 'Nguyễn Văn M', handle: '@nvm99', risk: 'high', reasonTag: 'flagged',
      reason: 'Thông tin sai lệch', reports: 12,
      preview: 'Mời mọi người chia sẻ rộng. Đã có nhiều người gặp tình trạng giảm trí nhớ sau khi tiêm liều thứ ba của vacxin...',
      meta: { topic: 'Y tế', sentiment: 'Tiêu cực', sensitivity: 72, trust: 18, keywords: ['vacxin', 'COVID-19', 'sức khỏe', 'tin giả?'] } },
    { id: 2, lead: 'Tài khoản giả mạo @vtcnews_real đăng tin giật gân',
      author: 'Vô danh', handle: '@vtcnews_real', risk: 'high', reasonTag: 'flagged',
      reason: 'Tài khoản giả mạo', reports: 8,
      preview: '"NÓNG: Sập cây cầu lớn nhất Hà Nội" — bài viết không dẫn nguồn chính thức, kèm ảnh đã qua chỉnh sửa.',
      meta: { topic: 'Xã hội', sentiment: 'Tiêu cực', sensitivity: 64, trust: 8, keywords: ['giả mạo', 'tin nóng', 'không dẫn nguồn'] } },
    { id: 3, lead: 'Spam quảng cáo crypto trong nhóm Kinh tế Việt Nam',
      author: 'Đặng Cường', handle: '@cuongdang', risk: 'med', reasonTag: 'flagged',
      reason: 'Spam', reports: 4,
      preview: '🚀 SIÊU PHẨM 2026! Mua coin XYZ ngay hôm nay để x100. Đăng ký nhóm Telegram (link đính kèm)...',
      meta: { topic: 'Tài chính', sentiment: 'Trung tính', sensitivity: 32, trust: 22, keywords: ['crypto', 'quảng cáo', 'lừa đảo?'] } },
    { id: 4, lead: 'Bình luận xúc phạm trong bài "Quy định nội dung AI"',
      author: 'Trần Phú', handle: '@phut', risk: 'med', reasonTag: 'flagged',
      reason: 'Ngôn từ kích động', reports: 5,
      preview: 'Cứ nói thẳng đi, đám "chuyên gia" này có hiểu gì đâu mà bày đặt phát biểu...',
      meta: { topic: 'Công nghệ', sentiment: 'Tiêu cực', sensitivity: 58, trust: 40, keywords: ['xúc phạm', 'kích động', 'cá nhân'] } },
    { id: 5, lead: 'Hình ảnh có dấu hiệu nhạy cảm chưa gắn nhãn',
      author: 'Lưu Bảo', handle: '@bao_l', risk: 'low', reasonTag: 'pending',
      reason: 'Nội dung nhạy cảm', reports: 2,
      preview: 'Ảnh chụp hiện trường tai nạn giao thông trên QL1A...',
      meta: { topic: 'Xã hội', sentiment: 'Trung tính', sensitivity: 70, trust: 65, keywords: ['tai nạn', 'hiện trường'] } },
  ];
  const [sel, setSel] = React.useState(items[0]);
  const [action, setAction] = React.useState(null);
  const doAct = (a) => { setAction(a); setTimeout(() => setAction(null), 1500); };

  const riskCls = {
    high: 'bg-rose-500/22 text-rose-700 dark:text-rose-300',
    med:  'bg-amber-500/22 text-amber-700 dark:text-amber-300',
    low:  'bg-blue-500/22 text-blue-700 dark:text-blue-300',
  };

  return (
    <>
      <AdminH title="Kiểm duyệt nội dung" sub="28 mục đang chờ. Ưu tiên theo rủi ro và số lượt báo cáo."
        right={<>
          <DateRange icon={<IA.Filter size={13}/>}>Mọi lý do</DateRange>
          <DateRange icon={<IA.Flame size={13}/>}>Sắp xếp: Rủi ro</DateRange>
          <button className={`${GA.btn} ${GA.btnInk} ${GA.btnSm}`}><IA.Check size={13}/> Duyệt nhanh đã chọn (5)</button>
        </>}/>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-5">
        <div className={`${GA.card} overflow-hidden`}>
          {items.map((it, i) => (
            <div key={it.id} onClick={() => setSel(it)}
              className={`px-5 py-4 cursor-pointer transition-colors ${i ? 'border-t border-ink/6 dark:border-white/6' : ''}
                ${sel.id === it.id
                  ? 'bg-gradient-to-r from-emerald-500/14 to-emerald-500/2 shadow-[inset_3px_0_0_#00A66B] pl-[22px]'
                  : 'hover:bg-white/40 dark:hover:bg-white/4'}`}>
              <div className="flex items-center gap-2 font-semibold text-[14px] leading-tight mb-1.5">
                <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.4)] ${riskCls[it.risk]}`}>
                  <IA.AlertCircle size={10}/> Rủi ro {it.risk === 'high' ? 'CAO' : it.risk === 'med' ? 'VỪA' : 'THẤP'}
                </span>
                {it.lead}
              </div>
              <div className="text-[13px] text-ink-2 dark:text-white/75 leading-snug mt-2 line-clamp-2">{it.preview}</div>
              <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[12px] text-muted dark:text-white/55">
                <span><b className="text-ink dark:text-white">{it.author}</b> · {it.handle}</span>
                <span>·</span><span>{it.reports} báo cáo</span>
                <span>·</span><ModBadge kind={it.reasonTag} label={it.reason}/>
              </div>
            </div>
          ))}
        </div>

        <aside className={`${GA.card} p-6 self-start sticky top-6`}>
          <h4 className="font-serif text-[16px] font-medium">Phân tích AI</h4>
          <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3.5">Gắn nhãn tự động — admin xác nhận cuối cùng.</p>

          <Section label="Bài viết">
            <div className="text-[14px] font-medium leading-snug">{sel.lead}</div>
            <div className="text-[12px] text-muted dark:text-white/55 mt-1.5">{sel.author} · {sel.handle}</div>
          </Section>

          <Section label="Metadata">
            <div className="flex flex-wrap gap-1.5 mb-3">
              <span className={GA.chip}><IA.Tag size={10}/>{sel.meta.topic}</span>
              <span className={GA.chip}>Sentiment: {sel.meta.sentiment}</span>
            </div>
            <Meter label="Độ nhạy cảm" value={sel.meta.sensitivity} tone="rose"/>
            <div className="mt-3"><Meter label="Độ tin cậy" value={sel.meta.trust} tone={sel.meta.trust > 60 ? 'emerald' : sel.meta.trust > 30 ? 'amber' : 'rose'}/></div>
          </Section>

          <Section label="Từ khóa chính">
            <div className="flex flex-wrap gap-1.5">
              {sel.meta.keywords.map((k, i) => <span key={i} className={`${GA.chip} ${GA.chipOutline}`}>{k}</span>)}
            </div>
          </Section>

          <Section label="Hành động">
            <div className="grid grid-cols-2 gap-2">
              <button className={`${GA.btn} ${GA.btnEmerald} ${GA.btnSm}`} onClick={() => doAct('Đã duyệt bài viết')}><IA.Check size={12}/> Duyệt</button>
              <button className={`${GA.btn} ${GA.btnGhost} ${GA.btnSm}`} onClick={() => doAct('Đã yêu cầu chỉnh sửa')}><IA.Edit size={12}/> Yêu cầu sửa</button>
              <button className={`${GA.btn} ${GA.btnGhost} ${GA.btnSm}`} onClick={() => doAct('Đã ẩn bài viết')}><IA.EyeOff size={12}/> Ẩn</button>
              <button className={`${GA.btn} ${GA.btnSm} bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30 backdrop-blur-md`} onClick={() => doAct('Đã khóa bài & tài khoản')}><IA.Flag size={12}/> Khóa</button>
            </div>
            {action && (
              <div className="mt-3 px-3 py-2.5 rounded-2xl bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 text-[12.5px] flex items-center gap-2">
                <IA.Check size={14}/> {action}.
              </div>
            )}
          </Section>
        </aside>
      </div>
    </>
  );
}

function Section({ label, children }) {
  return (
    <div className="py-3.5 border-t border-ink/6 dark:border-white/6 first:border-t-0 first:pt-0">
      <div className="text-[11px] uppercase tracking-[0.06em] text-muted dark:text-white/55 font-semibold mb-2">{label}</div>
      {children}
    </div>
  );
}

function Meter({ label, value, tone = 'emerald' }) {
  const toneCls = {
    emerald: 'from-[#00C480] to-[#008A57]',
    rose: 'from-[#E66B5A] to-[#B83A28]',
    amber: 'from-[#F3B845] to-[#C58A1F]',
    azure: 'from-[#5BA0E8] to-[#2E6FB5]',
  }[tone];
  return (
    <div>
      <div className="flex justify-between text-[12px] mb-1">
        <span>{label}</span><b>{value}/100</b>
      </div>
      <div className="h-1 bg-ink/8 dark:bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full bg-gradient-to-r ${toneCls}`} style={{ width: value + '%' }}/>
      </div>
    </div>
  );
}

function AdminRecommendations() {
  const ctrSeries = [6.2, 6.4, 6.1, 6.6, 6.8, 7.0, 6.7, 7.2, 7.0, 7.4, 7.1, 7.3, 7.5, 7.4];
  const saveSeries = [3.8, 4.0, 3.9, 4.1, 4.2, 4.3, 4.0, 4.4, 4.3, 4.5, 4.2, 4.5, 4.7, 4.6];
  return (
    <>
      <AdminH title="Hiệu quả đề xuất" sub="Theo dõi chất lượng feed cá nhân hóa và chất lượng nội dung được đề xuất."
        right={<>
          <DateRange icon={<IA.Clock size={13}/>}>14 ngày qua</DateRange>
          <button className={`${GA.btn} ${GA.btnGhost} ${GA.btnSm}`}><IA.Refresh size={13}/> Làm mới</button>
        </>}/>

      <div className="flex items-start gap-3 mb-4 p-4 px-5 rounded-3xl bg-gradient-to-br from-amber-500/22 to-amber-300/12 border border-amber-500/40 backdrop-blur-2xl shadow-glass-inner text-amber-700 dark:text-amber-300">
        <IA.AlertTriangle size={18} className="mt-1 flex-none"/>
        <div className="flex-1">
          <strong className="text-ink dark:text-white text-[14px] block mb-1">Cảnh báo: chủ đề "Crypto" đang được đề xuất tăng 68% so với tuần trước.</strong>
          <p className="text-ink-2 dark:text-white/80 text-[13px] leading-relaxed m-0">
            Phần lớn nội dung đến từ 4 tài khoản chưa xác minh. Tỷ lệ báo cáo cao gấp 3 lần mức trung bình. Cân nhắc giảm trọng số.
          </p>
        </div>
        <button className={`${GA.btn} ${GA.btnGhost} ${GA.btnSm}`}>Mở điều tra</button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3.5 mb-4">
        {[
          { lab: 'Precision@10', val: '72.4%', d: '+1.8pp' },
          { lab: 'Recall@10', val: '38.6%', d: '+0.6pp' },
          { lab: 'CTR feed', val: '6.8%', d: '+0.4pp' },
          { lab: 'Tỷ lệ lưu bài', val: '4.2%', d: '+0.2pp' },
          { lab: 'Tỷ lệ ẩn bài', val: '1.2%', d: '-0.1pp' },
        ].map((k, i) => (
          <div key={i} className={`${GA.card} p-4 px-4.5`}>
            <div className="text-[12px] text-muted dark:text-white/60 mb-2">{k.lab}</div>
            <div className="font-serif text-[26px] tracking-tight font-medium leading-none">{k.val}</div>
            <div className="mt-2.5 inline-flex items-center gap-1 text-[11.5px] font-semibold text-emerald-700 dark:text-emerald-400">
              <IA.ArrowUp size={11} style={{ transform: k.d.startsWith('-') ? 'rotate(180deg)' : '' }}/> {k.d}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-4">
        <div className={`${GA.card} p-6`}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h4 className="font-serif text-[17px] font-medium">CTR feed theo ngày</h4>
              <div className="text-[12px] text-muted dark:text-white/60 mt-1">So với tỷ lệ lưu bài.</div>
            </div>
            <div className="flex gap-3.5 text-[12px] text-muted dark:text-white/60 flex-wrap">
              <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-sm bg-emerald-500 inline-block"/> CTR</span>
              <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-sm bg-blue-500 inline-block"/> Save rate</span>
            </div>
          </div>
          <AreaChart data={ctrSeries.map(x => x * 10)} secondary={saveSeries.map(x => x * 10)} height={240}/>
        </div>

        <div className={`${GA.card} p-6`}>
          <h4 className="font-serif text-[17px] font-medium mb-1">Theo nguồn đề xuất</h4>
          <div className="text-[12px] text-muted dark:text-white/60 mb-4">Tỷ lệ tương tác theo loại tín hiệu.</div>
          <BarsHorizontal max={100} items={[
            { label: 'Theo sở thích cá nhân', value: 78, display: '78%' },
            { label: 'Theo người theo dõi',   value: 64, display: '64%', color: '#2E6FB5' },
            { label: 'Theo xu hướng',         value: 52, display: '52%', color: '#B58514' },
            { label: 'Theo nhóm',             value: 47, display: '47%', color: '#5C45A6' },
            { label: 'Theo nguồn xác minh',   value: 71, display: '71%', color: '#008A57' },
          ]}/>
        </div>
      </div>

      <div className={`${GA.card} p-6 mt-4`}>
        <h4 className="font-serif text-[17px] font-medium mb-3.5">Top bài được đề xuất nhiều nhất tuần này</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-muted dark:text-white/55 font-semibold border-b border-ink/8 dark:border-white/8">
                <th className="p-3 w-10">#</th>
                <th className="p-3">Bài viết</th>
                <th className="p-3">Chủ đề</th>
                <th className="p-3 text-right">Lượt đề xuất</th>
                <th className="p-3 text-right">CTR</th>
                <th className="p-3 text-right">Tỷ lệ lưu</th>
                <th className="p-3 text-right">Tỷ lệ ẩn</th>
                <th className="p-3 text-right">Đánh giá</th>
              </tr>
            </thead>
            <tbody>
              {DA.POSTS.map((p, i) => {
                const ctr = (4 + (i * 1.2) % 6).toFixed(1);
                const sav = (2 + (i * 0.9) % 4).toFixed(1);
                const hid = ((i * 0.3) % 1.6).toFixed(1);
                const ok = (parseFloat(ctr) + parseFloat(sav) - parseFloat(hid) * 2) > 7;
                return (
                  <tr key={p.id} className="border-b border-ink/6 dark:border-white/6 last:border-b-0 hover:bg-white/40 dark:hover:bg-white/4 transition-colors">
                    <td className="p-3.5 text-muted font-serif text-[16px]">{i + 1}</td>
                    <td className="p-3.5">
                      <div className="font-semibold text-[13.5px] mb-0.5">{p.title}</div>
                      <div className="text-[11.5px] text-muted dark:text-white/55">{p.author.name}</div>
                    </td>
                    <td className="p-3.5"><span className={GA.chip}>{DA.TOPICS.find(t => t.id === p.tags[0])?.name}</span></td>
                    <td className="p-3.5 text-right tabular-nums">{(120 - i * 12).toFixed(0)}K</td>
                    <td className="p-3.5 text-right tabular-nums">{ctr}%</td>
                    <td className="p-3.5 text-right tabular-nums">{sav}%</td>
                    <td className={`p-3.5 text-right tabular-nums ${hid > 1 ? 'text-rose-600' : ''}`}>{hid}%</td>
                    <td className="p-3.5 text-right">
                      <span className={`${GA.badgeBase} ${ok ? GA.badgeVerified : GA.badgePending}`}>
                        {ok ? <><IA.Check size={10}/> Tốt</> : <><IA.AlertCircle size={10}/> Theo dõi</>}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { AdminShell, AdminOverview, AdminModeration, AdminRecommendations });
