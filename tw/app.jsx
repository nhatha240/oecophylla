/* App router + Tweaks panel — Tailwind version */
const { useState: useStateAppTw, useEffect: useEffectAppTw } = React;
const GR = window.G;
const IR = window.I;

const TWEAKS_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweak] = window.useTweaks(TWEAKS_DEFAULTS);
  const [screen, setScreen] = useStateAppTw('feed');
  const [adminPage, setAdminPage] = useStateAppTw('overview');
  const [openPost, setOpenPost] = useStateAppTw(null);
  const [toast, setToast] = useStateAppTw(null);

  const theme = tweaks.theme || 'light';
  useEffectAppTw(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffectAppTw(() => {
    const onNav = (e) => {
      const t = e.detail;
      if (t === 'auth')          setScreen('auth');
      else if (t === 'onboarding') setScreen('onboarding');
      else if (t === 'feed')     { setScreen('feed'); setOpenPost(null); }
      else if (t === 'article')  { setScreen('article'); setOpenPost(window.DATA.POSTS[0]); }
      else if (t === 'explore')  setScreen('explore');
      else if (t === 'profile')  setScreen('profile');
      else if (t === 'notif')    setScreen('notif');
      else if (t === 'mobile')   setScreen('mobile');
      else if (t === 'admin')      { setScreen('admin'); setAdminPage('overview'); }
      else if (t === 'admin-mod')  { setScreen('admin'); setAdminPage('mod'); }
      else if (t === 'admin-rec')  { setScreen('admin'); setAdminPage('rec'); }
    };
    window.addEventListener('oc-nav', onNav);
    return () => window.removeEventListener('oc-nav', onNav);
  }, []);

  const showToast = (msg) => setToast(msg);
  const isAdmin = screen === 'admin';
  const isAuth = screen === 'auth' || screen === 'onboarding';
  const isMobile = screen === 'mobile';

  const crumbs = {
    feed:    <>Bảng tin <em className="not-italic text-muted">· Dành cho bạn</em></>,
    explore: <>Khám phá</>,
    notif:   <>Thông báo</>,
    profile: <>Hồ sơ của bạn</>,
    saved:   <>Đã lưu</>,
    follow:  <>Đang theo dõi</>,
    group:   <>Nhóm</>,
    article: <>Bài viết <em className="not-italic text-muted">· chi tiết</em></>,
  }[screen];

  if (isAuth) {
    if (screen === 'auth') return <AuthScreen onContinue={() => setScreen('onboarding')}/>;
    return <Onboarding onDone={() => { setScreen('feed'); showToast('Bảng tin của bạn đã sẵn sàng!'); }}/>;
  }

  if (isMobile) {
    return (
      <>
        <Topbar crumbs={<>Mobile preview</>} search={false}
          theme={theme} onTheme={() => setTweak({ theme: theme === 'dark' ? 'light' : 'dark' })}/>
        <MobilePreview onBack={() => setScreen('feed')}/>
        {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
      </>
    );
  }

  if (isAdmin) {
    return (
      <>
        <AdminShell page={adminPage} onNav={p => setAdminPage(p)} onExit={() => setScreen('feed')}>
          {adminPage === 'overview' && <AdminOverview/>}
          {adminPage === 'mod' && <AdminModeration/>}
          {adminPage === 'rec' && <AdminRecommendations/>}
          {adminPage === 'flagged' && <AdminModeration/>}
          {!['overview','mod','rec','flagged'].includes(adminPage) && <AdminPlaceholder page={adminPage} onJump={p => setAdminPage(p)}/>}
        </AdminShell>
        {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
      </>
    );
  }

  return (
    <div className="grid grid-cols-[232px_1fr] min-h-screen">
      <Sidebar
        active={screen === 'article' ? 'feed' : screen}
        counts={{ notif: 3 }}
        onNav={s => { setScreen(s); setOpenPost(null); }}
      />
      <div className="min-w-0">
        <Topbar
          crumbs={crumbs}
          theme={theme}
          onTheme={() => setTweak({ theme: theme === 'dark' ? 'light' : 'dark' })}
          onAdmin={() => { setScreen('admin'); setAdminPage('overview'); }}
          right={
            <button onClick={() => setScreen('mobile')} className={`${GR.btn} ${GR.btnGhost} ${GR.btnSm}`}>
              <IR.Globe size={13}/> Xem mobile
            </button>
          }
        />
        {screen === 'feed' && <Feed onOpenPost={p => { setOpenPost(p); setScreen('article'); }} toast={showToast}/>}
        {screen === 'article' && <Reader post={openPost} onBack={() => setScreen('feed')} toast={showToast}/>}
        {screen === 'explore' && <Explore onOpenPost={p => { setOpenPost(p); setScreen('article'); }}/>}
        {screen === 'profile' && <Profile/>}
        {screen === 'notif' && <Notifications/>}
        {(screen === 'saved' || screen === 'follow' || screen === 'group') && <ScreenPlaceholder screen={screen} onBack={() => setScreen('feed')}/>}
      </div>
      {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
    </div>
  );
}

function ScreenPlaceholder({ screen, onBack }) {
  const titles = {
    saved:  ['Đã lưu', 'Bộ sưu tập bài viết bạn đã lưu để đọc sau.'],
    follow: ['Đang theo dõi', 'Bài mới từ tác giả và nhóm bạn theo dõi.'],
    group:  ['Nhóm', 'Cộng đồng theo chủ đề.'],
  };
  const [title, sub] = titles[screen];
  return (
    <div className="max-w-[720px] mx-auto py-16 px-8 text-center">
      <h2 className="font-serif text-[32px] font-medium tracking-tight mb-2">{title}</h2>
      <p className="text-muted dark:text-white/60 text-[15px] mb-6">{sub}</p>
      <div className={`${GR.card} p-7 text-left`}>
        <IR.Layers size={22} className="text-muted"/>
        <h3 className="font-serif text-[20px] font-medium tracking-tight mt-3 mb-1.5">Màn hình này phác thảo cho giai đoạn tiếp theo.</h3>
        <p className="text-muted dark:text-white/60 text-[14px] leading-relaxed">
          Các flow chính tập trung ở: <b>Đăng nhập</b> → <b>Onboarding</b> → <b>Home Feed</b>, với chi tiết bài viết, Khám phá,
          Hồ sơ, Thông báo, Admin Dashboard và bản xem mobile. Trang <b>{title}</b> dùng layout tương tự Home Feed lọc theo ngữ cảnh.
        </p>
        <div className="flex gap-2 mt-4">
          <button onClick={onBack} className={`${GR.btn} ${GR.btnEmerald} ${GR.btnSm}`}><IR.ArrowLeft size={12}/> Trở về bảng tin</button>
        </div>
      </div>
    </div>
  );
}

function AdminPlaceholder({ page, onJump }) {
  const titles = {
    posts:   ['Quản lý bài viết',       'Danh sách bài đã đăng, theo nguồn và trạng thái kiểm duyệt.'],
    users:   ['Quản lý người dùng',     'Tài khoản, vai trò, lịch sử hành vi, hành động kiểm duyệt.'],
    groups:  ['Quản lý nhóm',           'Trạng thái nhóm, chính sách đăng, quản trị viên.'],
    topics:  ['Chủ đề / Metadata',      'Cấu hình taxonomy, alias, quan hệ topic-topic.'],
    reports: ['Báo cáo người dùng',     'Hàng đợi báo cáo theo lý do và mức độ rủi ro.'],
    logs:    ['Nhật ký hệ thống',       'Sự kiện hệ thống, audit log, hành động admin.'],
  };
  const [t, s] = titles[page] || ['—', '—'];
  return (
    <>
      <div className="mb-6">
        <h2 className="font-serif text-[28px] font-medium tracking-tight">{t}</h2>
        <div className="text-[13px] text-muted dark:text-white/60 mt-1">{s}</div>
      </div>
      <div className={`${GR.card} p-10 text-center`}>
        <IR.Layers size={28} className="mx-auto text-muted"/>
        <h3 className="font-serif text-[20px] font-medium tracking-tight mt-3 mb-1.5">Trang này phác thảo cho giai đoạn tiếp theo.</h3>
        <p className="text-muted dark:text-white/60 text-[14px] leading-relaxed max-w-[520px] mx-auto">
          3 trang admin trọng tâm đang hoạt động đầy đủ: <b>Tổng quan</b>, <b>Kiểm duyệt nội dung</b> và <b>Hiệu quả đề xuất</b>.
        </p>
        <div className="flex gap-2 mt-4 justify-center">
          <button className={`${GR.btn} ${GR.btnEmerald} ${GR.btnSm}`} onClick={() => onJump('overview')}>Tổng quan</button>
          <button className={`${GR.btn} ${GR.btnGhost} ${GR.btnSm}`} onClick={() => onJump('mod')}>Kiểm duyệt</button>
          <button className={`${GR.btn} ${GR.btnGhost} ${GR.btnSm}`} onClick={() => onJump('rec')}>Hiệu quả đề xuất</button>
        </div>
      </div>
    </>
  );
}

function OcTweaks() {
  const [tweaks, setTweak] = window.useTweaks(TWEAKS_DEFAULTS);
  const { TweaksPanel, TweakSection, TweakRadio, TweakButton } = window;
  const go = (t) => window.dispatchEvent(new CustomEvent('oc-nav', { detail: t }));
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection label="Giao diện">
        <TweakRadio
          label="Chế độ"
          value={tweaks.theme}
          onChange={v => setTweak({ theme: v })}
          options={[
            { value: 'light', label: 'Sáng' },
            { value: 'dark',  label: 'Tối' },
          ]}
        />
      </TweakSection>
      <TweakSection label="Mở nhanh màn hình">
        <TweakButton label="1. Đăng nhập / Đăng ký" onClick={() => go('auth')}/>
        <TweakButton label="2. Onboarding" secondary onClick={() => go('onboarding')}/>
        <TweakButton label="3. Home Feed" secondary onClick={() => go('feed')}/>
        <TweakButton label="4. Chi tiết bài viết" secondary onClick={() => go('article')}/>
        <TweakButton label="5. Khám phá" secondary onClick={() => go('explore')}/>
        <TweakButton label="6. Hồ sơ" secondary onClick={() => go('profile')}/>
        <TweakButton label="7. Thông báo" secondary onClick={() => go('notif')}/>
        <TweakButton label="8. Xem mobile" secondary onClick={() => go('mobile')}/>
        <TweakButton label="9. Admin · Tổng quan" secondary onClick={() => go('admin')}/>
        <TweakButton label="10. Admin · Kiểm duyệt" secondary onClick={() => go('admin-mod')}/>
        <TweakButton label="11. Admin · Hiệu quả đề xuất" secondary onClick={() => go('admin-rec')}/>
      </TweakSection>
    </TweaksPanel>
  );
}

function Root() {
  return <><App/><OcTweaks/></>;
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<Root/>);
