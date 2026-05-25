/* Admin: shell + overview + moderation + recommendation effectiveness */

function AdminShell({ children, page, onNav, onExit }) {
  const items = [
    { sec: 'Bảng điều khiển' },
    { id: 'overview',  name: 'Tổng quan',           icon: 'ChartBar' },
    { id: 'posts',     name: 'Quản lý bài viết',    icon: 'FileText' },
    { id: 'flagged',   name: 'Bài bị gắn cờ',       icon: 'Flag', count: 14 },
    { id: 'mod',       name: 'Kiểm duyệt nội dung', icon: 'Shield', count: 28 },
    { sec: 'Cộng đồng' },
    { id: 'users',     name: 'Quản lý người dùng',  icon: 'Users' },
    { id: 'groups',    name: 'Quản lý nhóm',        icon: 'Group' },
    { id: 'topics',    name: 'Chủ đề / Metadata',   icon: 'Tag' },
    { id: 'reports',   name: 'Báo cáo người dùng',  icon: 'AlertTriangle', count: 6 },
    { sec: 'Hệ thống' },
    { id: 'rec',       name: 'Hiệu quả đề xuất',    icon: 'Activity' },
    { id: 'logs',      name: 'Nhật ký hệ thống',    icon: 'Database' },
  ];
  return (
    <div className="admin-shell" data-screen-label="09 Admin">
      <aside className="admin-sidebar">
        <div className="brand" onClick={onExit} style={{ cursor: 'pointer' }}>
          <div className="brand-mark" style={{ background: 'var(--emerald-500)' }}>O</div>
          <div className="brand-name">Oecophy<em>lla</em></div>
        </div>
        <div className="admin-sidebar-tag">
          <I.Shield size={12} /> Khu vực Quản trị
        </div>
        <nav className="nav">
          {items.map((it, i) => {
            if (it.sec) return <div key={i} className="nav-section">{it.sec}</div>;
            const Ic = I[it.icon];
            return (
              <button key={it.id} className={`nav-item ${page === it.id ? 'active' : ''}`} onClick={() => onNav(it.id)}>
                <Ic size={16} />
                <span>{it.name}</span>
                {it.count != null && <span className="count">{it.count}</span>}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <button className="nav-item" onClick={onExit}>
            <I.ArrowLeft size={16}/>
            <span>Trở về Oecophylla</span>
          </button>
          <div className="profile-card" style={{ marginTop: 8 }}>
            <Avatar author={window.DATA.AUTHORS[5]} size="s32" />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="name" style={{ color: 'var(--paper)' }}>Bùi Khánh Linh</div>
              <div className="handle">Senior Moderator</div>
            </div>
          </div>
        </div>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  );
}

function AdminOverview() {
  const kpis = [
    { lab: 'Tổng người dùng',       val: '184.2K', delta: '+2.4%', dir: 'up' },
    { lab: 'Bài viết hôm nay',      val: '3.812',  delta: '+12%',  dir: 'up' },
    { lab: 'Bài chờ duyệt',         val: '142',    delta: '-8%',   dir: 'down' },
    { lab: 'Báo cáo vi phạm',       val: '38',     delta: '+5',    dir: 'down' },
    { lab: 'Tỷ lệ tương tác',       val: '6.8%',   delta: '+0.4pp',dir: 'up' },
    { lab: 'Tỷ lệ bài bị ẩn',       val: '1.2%',   delta: '-0.1pp',dir: 'up' },
  ];

  const series = [42, 58, 51, 64, 72, 68, 81, 75, 92, 88, 96, 110, 102, 121];
  const compare = [38, 50, 47, 55, 60, 58, 64, 62, 71, 68, 70, 78, 75, 88];

  return (
    <>
      <div className="admin-h">
        <div>
          <h2>Tổng quan</h2>
          <div className="sub">Sức khỏe của Oecophylla trong 7 ngày qua. Cập nhật lần cuối 3 phút trước.</div>
        </div>
        <div className="admin-h-actions">
          <div className="date-range"><I.Clock size={13}/> 7 ngày qua <I.Chevron size={11}/></div>
          <button className="btn ghost sm"><I.Refresh size={13}/> Làm mới</button>
          <button className="btn primary sm"><I.FileText size={13}/> Xuất báo cáo</button>
        </div>
      </div>

      <div className="kpi-grid">
        {kpis.map((k, i) => {
          // For Bài chờ duyệt: down = good; for Báo cáo vi phạm: up = bad
          const goodDown = i === 2 || i === 5;
          const goodUp = i !== 2 && i !== 3 && i !== 5;
          const isGood = k.dir === 'up' ? goodUp : goodDown;
          const cls = isGood ? 'up' : 'down';
          return (
            <div key={i} className="kpi">
              <div className="label">{k.lab}</div>
              <div className="value">{k.val}</div>
              <div className={`delta ${cls}`}>
                {k.dir === 'up' ? <I.ArrowUp size={11}/> : <I.ArrowUp size={11} style={{ transform: 'rotate(180deg)' }}/>}
                {k.delta} so với tuần trước
              </div>
            </div>
          );
        })}
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <div className="head">
            <div>
              <h4>Xu hướng bài viết theo ngày</h4>
              <div className="sub">Tổng bài đăng và bài được duyệt qua kiểm duyệt tự động.</div>
            </div>
            <div className="chart-legend">
              <span><i style={{ background: 'var(--emerald-500)' }}/> Tổng bài</span>
              <span><i style={{ background: 'var(--muted-2)' }}/> Tuần trước</span>
            </div>
          </div>
          <AreaChart data={series} secondary={compare} height={220}/>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
            <span>17/05</span><span>19/05</span><span>21/05</span><span>23/05</span><span>Hôm nay</span>
          </div>
        </div>

        <div className="chart-card">
          <div className="head">
            <div>
              <h4>Phân bố chủ đề</h4>
              <div className="sub">12.4K bài hôm nay</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <Donut size={150} hole={48} label={{ value: '12.4K', sub: 'bài hôm nay' }} slices={[
              { value: 32, color: 'var(--emerald-500)' },
              { value: 22, color: 'var(--azure-500)' },
              { value: 18, color: 'var(--amber-500)' },
              { value: 14, color: 'var(--violet-500)' },
              { value: 8,  color: 'var(--rose-500)' },
              { value: 6,  color: 'var(--muted-2)' },
            ]}/>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              {[
                ['Công nghệ', 32, 'var(--emerald-500)'],
                ['Kinh tế',   22, 'var(--azure-500)'],
                ['Đời sống',  18, 'var(--amber-500)'],
                ['AI',        14, 'var(--violet-500)'],
                ['Xã hội',     8, 'var(--rose-500)'],
                ['Khác',       6, 'var(--muted-2)'],
              ].map(([n, v, c]) => (
                <div key={n} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: c, display: 'inline-block' }}/> {n}
                  </span>
                  <b style={{ fontWeight: 600 }}>{v}%</b>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="chart-grid" style={{ marginTop: 16 }}>
        <div className="chart-card">
          <div className="head">
            <div>
              <h4>Chất lượng đề xuất</h4>
              <div className="sub">So sánh hiệu quả các nguồn đề xuất.</div>
            </div>
            <a className="link" style={{ color: 'var(--emerald-700)', fontSize: 13, fontWeight: 600 }}>Xem chi tiết →</a>
          </div>
          <BarsHorizontal items={[
            { label: 'CTR feed',              value: 6.8, display: '6.8%' },
            { label: 'Tỷ lệ lưu bài',         value: 4.2, display: '4.2%', color: 'var(--azure-500)' },
            { label: 'Tỷ lệ ẩn bài',          value: 1.2, display: '1.2%', color: 'var(--rose-500)' },
            { label: 'Thời gian đọc TB (s)',  value: 4.7, display: '128 giây', color: 'var(--amber-500)' },
          ]} max={8}/>
        </div>

        <div className="chart-card">
          <h4 style={{ marginBottom: 16 }}>Nội dung cần xử lý gấp</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { lead: 'Bài viết về vacxin COVID có dấu hiệu sai lệch', tag: 'flagged', meta: '12 báo cáo · Rủi ro CAO' },
              { lead: 'Tài khoản giả mạo @vtcnews_real', tag: 'flagged', meta: '8 báo cáo · Rủi ro CAO' },
              { lead: 'Bình luận quấy rối trong nhóm Khoa học mở', tag: 'pending', meta: '3 báo cáo · Rủi ro VỪA' },
              { lead: 'Spam quảng cáo crypto lặp lại', tag: 'flagged', meta: '4 báo cáo · Rủi ro VỪA' },
            ].map((r, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: 10, borderRadius: 10, background: 'var(--surface-2)', alignItems: 'center' }}>
                <span className={`badge ${r.tag}`}><I.AlertCircle size={11}/></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.lead}</div>
                  <div className="t-meta">{r.meta}</div>
                </div>
                <button className="btn primary sm">Xem</button>
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
    {
      id: 1, lead: 'Bài viết cho rằng vacxin COVID gây tổn thương trí nhớ',
      author: 'Nguyễn Văn M', handle: '@nvm99', risk: 'high', reasonTag: 'flagged',
      reason: 'Thông tin sai lệch', reports: 12,
      preview: 'Mời mọi người chia sẻ rộng. Đã có nhiều người gặp tình trạng giảm trí nhớ sau khi tiêm liều thứ ba của vacxin...',
      meta: { topic: 'Y tế', sentiment: 'Tiêu cực', sensitivity: 72, trust: 18, keywords: ['vacxin', 'COVID-19', 'sức khỏe', 'tin giả?'] }
    },
    {
      id: 2, lead: 'Tài khoản giả mạo @vtcnews_real đăng tin giật gân',
      author: 'Vô danh', handle: '@vtcnews_real', risk: 'high', reasonTag: 'flagged',
      reason: 'Tài khoản giả mạo', reports: 8,
      preview: '“NÓNG: Sập cây cầu lớn nhất Hà Nội” — bài viết không dẫn nguồn chính thức, kèm ảnh đã qua chỉnh sửa.',
      meta: { topic: 'Xã hội', sentiment: 'Tiêu cực', sensitivity: 64, trust: 8, keywords: ['giả mạo', 'tin nóng', 'không dẫn nguồn'] }
    },
    {
      id: 3, lead: 'Spam quảng cáo crypto trong nhóm Kinh tế Việt Nam',
      author: 'Đặng Cường', handle: '@cuongdang', risk: 'med', reasonTag: 'flagged',
      reason: 'Spam', reports: 4,
      preview: '🚀 SIÊU PHẨM 2026! Mua coin XYZ ngay hôm nay để x100. Đăng ký nhóm Telegram (link đính kèm)...',
      meta: { topic: 'Tài chính', sentiment: 'Trung tính', sensitivity: 32, trust: 22, keywords: ['crypto', 'quảng cáo', 'lừa đảo?'] }
    },
    {
      id: 4, lead: 'Bình luận xúc phạm trong bài “Quy định nội dung AI”',
      author: 'Trần Phú', handle: '@phut', risk: 'med', reasonTag: 'flagged',
      reason: 'Ngôn từ kích động', reports: 5,
      preview: 'Cứ nói thẳng đi, đám “chuyên gia” này có hiểu gì đâu mà bày đặt phát biểu...',
      meta: { topic: 'Công nghệ', sentiment: 'Tiêu cực', sensitivity: 58, trust: 40, keywords: ['xúc phạm', 'kích động', 'cá nhân'] }
    },
    {
      id: 5, lead: 'Hình ảnh có dấu hiệu nhạy cảm chưa gắn nhãn',
      author: 'Lưu Bảo', handle: '@bao_l', risk: 'low', reasonTag: 'pending',
      reason: 'Nội dung nhạy cảm', reports: 2,
      preview: 'Ảnh chụp hiện trường tai nạn giao thông trên QL1A...',
      meta: { topic: 'Xã hội', sentiment: 'Trung tính', sensitivity: 70, trust: 65, keywords: ['tai nạn', 'hiện trường'] }
    },
  ];
  const [sel, setSel] = React.useState(items[0]);
  const [action, setAction] = React.useState(null);

  const doAct = (a) => {
    setAction(a);
    setTimeout(() => setAction(null), 1500);
  };

  return (
    <>
      <div className="admin-h">
        <div>
          <h2>Kiểm duyệt nội dung</h2>
          <div className="sub">28 mục đang chờ. Ưu tiên theo rủi ro và số lượt báo cáo.</div>
        </div>
        <div className="admin-h-actions">
          <div className="date-range"><I.Filter size={13}/> Mọi lý do <I.Chevron size={11}/></div>
          <div className="date-range"><I.Flame size={13}/> Sắp xếp: Rủi ro <I.Chevron size={11}/></div>
          <button className="btn primary sm"><I.Check size={13}/> Duyệt nhanh đã chọn (5)</button>
        </div>
      </div>

      <div className="mod-grid">
        <div className="mod-list">
          {items.map(it => (
            <div key={it.id} className={`mod-row ${sel.id === it.id ? 'selected' : ''}`} onClick={() => setSel(it)}>
              <div>
                <div className="lead">
                  <span className={`risk ${it.risk}`}>
                    <I.AlertCircle size={10}/>
                    Rủi ro {it.risk === 'high' ? 'CAO' : it.risk === 'med' ? 'VỪA' : 'THẤP'}
                  </span>
                  {it.lead}
                </div>
                <div className="preview-line">{it.preview}</div>
                <div className="meta">
                  <span><b style={{ color: 'var(--ink)' }}>{it.author}</b> · {it.handle}</span>
                  <span>·</span>
                  <span>{it.reports} báo cáo</span>
                  <span>·</span>
                  <span><ModBadge kind={it.reasonTag} label={it.reason} /></span>
                </div>
              </div>
              <div style={{ alignSelf: 'flex-start' }}>
                <button className="icon-btn"><I.Chevron size={14}/></button>
              </div>
            </div>
          ))}
        </div>

        <aside className="mod-detail">
          <h4>Phân tích AI</h4>
          <p className="t-meta" style={{ margin: '-4px 0 14px' }}>Gắn nhãn tự động — admin xác nhận cuối cùng.</p>

          <div className="mod-section">
            <div className="lab">Bài viết</div>
            <div style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.35 }}>{sel.lead}</div>
            <div className="t-meta" style={{ marginTop: 6 }}>{sel.author} · {sel.handle}</div>
          </div>

          <div className="mod-section">
            <div className="lab">Metadata</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              <span className="chip"><I.Tag size={10}/>{sel.meta.topic}</span>
              <span className="chip">Sentiment: {sel.meta.sentiment}</span>
            </div>

            <div className="mod-meter">
              <div className="row"><span>Độ nhạy cảm</span><b>{sel.meta.sensitivity}/100</b></div>
              <div className="track"><div className="fill rose" style={{ width: sel.meta.sensitivity + '%' }}/></div>
            </div>
            <div className="mod-meter" style={{ marginTop: 10 }}>
              <div className="row"><span>Độ tin cậy</span><b>{sel.meta.trust}/100</b></div>
              <div className="track"><div className={`fill ${sel.meta.trust > 60 ? '' : sel.meta.trust > 30 ? 'amber' : 'rose'}`} style={{ width: sel.meta.trust + '%' }}/></div>
            </div>
          </div>

          <div className="mod-section">
            <div className="lab">Từ khóa chính</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {sel.meta.keywords.map((k, i) => (
                <span key={i} className="chip outline">{k}</span>
              ))}
            </div>
          </div>

          <div className="mod-section">
            <div className="lab">Hành động</div>
            <div className="mod-actions">
              <button className="btn emerald sm" onClick={() => doAct('Đã duyệt bài viết')}><I.Check size={12}/> Duyệt</button>
              <button className="btn ghost sm" onClick={() => doAct('Đã yêu cầu chỉnh sửa')}><I.Edit size={12}/> Yêu cầu sửa</button>
              <button className="btn ghost sm" onClick={() => doAct('Đã ẩn bài viết')}><I.EyeOff size={12}/> Ẩn</button>
              <button className="btn ghost sm" style={{ color: 'var(--rose-500)', borderColor: 'color-mix(in oklab, var(--rose-500) 30%, transparent)' }} onClick={() => doAct('Đã khóa bài & tài khoản')}><I.Flag size={12}/> Khóa</button>
            </div>
            {action && (
              <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--emerald-50)', color: 'var(--emerald-700)', borderRadius: 10, fontSize: 12.5, display: 'flex', gap: 8, alignItems: 'center' }}>
                <I.Check size={14}/> {action}. Cập nhật trong bộ nhớ phiên.
              </div>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}

function AdminRecommendations() {
  const ctrSeries = [6.2, 6.4, 6.1, 6.6, 6.8, 7.0, 6.7, 7.2, 7.0, 7.4, 7.1, 7.3, 7.5, 7.4];
  const saveSeries = [3.8, 4.0, 3.9, 4.1, 4.2, 4.3, 4.0, 4.4, 4.3, 4.5, 4.2, 4.5, 4.7, 4.6];
  return (
    <>
      <div className="admin-h">
        <div>
          <h2>Hiệu quả đề xuất</h2>
          <div className="sub">Theo dõi chất lượng feed cá nhân hóa và chất lượng nội dung được đề xuất.</div>
        </div>
        <div className="admin-h-actions">
          <div className="date-range"><I.Clock size={13}/> 14 ngày qua <I.Chevron size={11}/></div>
          <button className="btn ghost sm"><I.Refresh size={13}/> Làm mới</button>
        </div>
      </div>

      <div className="alert-card">
        <I.AlertTriangle size={18} style={{ marginTop: 2, flex: 'none' }}/>
        <div className="body">
          <strong>Cảnh báo: chủ đề “Crypto” đang được đề xuất tăng 68% so với tuần trước.</strong>
          <p>Phần lớn nội dung đến từ 4 tài khoản chưa xác minh. Tỷ lệ báo cáo cao gấp 3 lần mức trung bình. Cân nhắc giảm trọng số cho cụm tài khoản này.</p>
        </div>
        <button className="btn ghost sm">Mở điều tra</button>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        {[
          { lab: 'Precision@10', val: '72.4%', delta: '+1.8pp', dir: 'up' },
          { lab: 'Recall@10',    val: '38.6%', delta: '+0.6pp', dir: 'up' },
          { lab: 'CTR feed',     val: '6.8%',  delta: '+0.4pp', dir: 'up' },
          { lab: 'Tỷ lệ lưu bài',val: '4.2%',  delta: '+0.2pp', dir: 'up' },
          { lab: 'Tỷ lệ ẩn bài', val: '1.2%',  delta: '-0.1pp', dir: 'up' },
        ].map((k, i) => (
          <div key={i} className="kpi">
            <div className="label">{k.lab}</div>
            <div className="value">{k.val}</div>
            <div className={`delta up`}><I.ArrowUp size={11}/> {k.delta}</div>
          </div>
        ))}
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <div className="head">
            <div>
              <h4>CTR feed theo ngày</h4>
              <div className="sub">So với tỷ lệ lưu bài.</div>
            </div>
            <div className="chart-legend">
              <span><i style={{ background: 'var(--emerald-500)' }}/> CTR (%)</span>
              <span><i style={{ background: 'var(--azure-500)' }}/> Save rate (%)</span>
            </div>
          </div>
          <AreaChart data={ctrSeries.map(x => x * 10)} secondary={saveSeries.map(x => x * 10)} height={240}/>
        </div>

        <div className="chart-card">
          <h4>Theo nguồn đề xuất</h4>
          <div className="sub" style={{ marginBottom: 18 }}>Tỷ lệ tương tác theo loại tín hiệu.</div>
          <BarsHorizontal max={100} items={[
            { label: 'Theo sở thích cá nhân', value: 78, display: '78%' },
            { label: 'Theo người theo dõi',   value: 64, display: '64%', color: 'var(--azure-500)' },
            { label: 'Theo xu hướng',         value: 52, display: '52%', color: 'var(--amber-500)' },
            { label: 'Theo nhóm',             value: 47, display: '47%', color: 'var(--violet-500)' },
            { label: 'Theo nguồn xác minh',   value: 71, display: '71%', color: 'var(--emerald-600)' },
          ]}/>
        </div>
      </div>

      <div className="chart-card" style={{ marginTop: 16 }}>
        <h4 style={{ marginBottom: 14 }}>Top bài được đề xuất nhiều nhất tuần này</h4>
        <table className="admin-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th>Bài viết</th>
              <th>Chủ đề</th>
              <th style={{ textAlign: 'right' }}>Lượt đề xuất</th>
              <th style={{ textAlign: 'right' }}>CTR</th>
              <th style={{ textAlign: 'right' }}>Tỷ lệ lưu</th>
              <th style={{ textAlign: 'right' }}>Tỷ lệ ẩn</th>
              <th style={{ textAlign: 'right' }}>Đánh giá</th>
            </tr>
          </thead>
          <tbody>
            {window.DATA.POSTS.map((p, i) => {
              const ctr = (4 + Math.random() * 6).toFixed(1);
              const sav = (2 + Math.random() * 4).toFixed(1);
              const hid = (Math.random() * 1.6).toFixed(1);
              const score = parseFloat(ctr) + parseFloat(sav) - parseFloat(hid) * 2;
              const ok = score > 7;
              return (
                <tr key={p.id}>
                  <td style={{ color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontSize: 16 }}>{i + 1}</td>
                  <td>
                    <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 2 }}>{p.title}</div>
                    <div className="t-meta">{p.author.name}</div>
                  </td>
                  <td>
                    <span className="chip">{window.DATA.TOPICS.find(t => t.id === p.tags[0])?.name}</span>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{(120 - i * 12).toFixed(0)}K</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{ctr}%</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{sav}%</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: hid > 1 ? 'var(--rose-500)' : 'inherit' }}>{hid}%</td>
                  <td style={{ textAlign: 'right' }}>
                    <span className={`badge ${ok ? 'verified-src' : 'pending'}`}>
                      {ok ? <><I.Check size={10}/> Tốt</> : <><I.AlertCircle size={10}/> Theo dõi</>}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

Object.assign(window, { AdminShell, AdminOverview, AdminModeration, AdminRecommendations });
