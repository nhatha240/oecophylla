/* Oecophylla — App entry. Top-level router that switches between screens. */

const { useState: useStateApp, useEffect: useEffectApp } = React;

const TWEAKS_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweak] = window.useTweaks(TWEAKS_DEFAULTS);
  const [screen, setScreen] = useStateApp('feed');
  const [adminPage, setAdminPage] = useStateApp('overview');
  const [openPost, setOpenPost] = useStateApp(null);
  const [toast, setToast] = useStateApp(null);
  const [notifOpen, setNotifOpen] = useStateApp(false);

  const theme = tweaks.theme || 'light';
  useEffectApp(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Listen for navigation events from the Tweaks panel.
  useEffectApp(() => {
    const onNav = (e) => {
      const t = e.detail;
      if (t === 'auth')        { setScreen('auth'); }
      else if (t === 'onboarding') { setScreen('onboarding'); }
      else if (t === 'feed')   { setScreen('feed'); setOpenPost(null); }
      else if (t === 'article'){ setScreen('article'); setOpenPost(window.DATA.POSTS[0]); }
      else if (t === 'explore'){ setScreen('explore'); }
      else if (t === 'profile'){ setScreen('profile'); }
      else if (t === 'notif')  { setNotifOpen(true); }
      else if (t === 'mobile') { setScreen('mobile'); }
      else if (t === 'admin')      { setScreen('admin'); setAdminPage('overview'); }
      else if (t === 'admin-mod')  { setScreen('admin'); setAdminPage('mod'); }
      else if (t === 'admin-rec')  { setScreen('admin'); setAdminPage('rec'); }
    };
    window.addEventListener('oc-nav', onNav);
    return () => window.removeEventListener('oc-nav', onNav);
  }, []);

  const showToast = (msg) => { setToast(msg); };

  const isAdmin = screen === 'admin';
  const isAuth = screen === 'auth' || screen === 'onboarding';
  const isMobile = screen === 'mobile';

  const crumbs = {
    feed:    <>Bảng tin <em>· Dành cho bạn</em></>,
    explore: <>Khám phá</>,
    notif:   <>Thông báo</>,
    profile: <>Hồ sơ của bạn</>,
    saved:   <>Đã lưu</>,
    follow:  <>Đang theo dõi</>,
    group:   <>Nhóm</>,
    article: <>Bài viết <em>· chi tiết</em></>,
  }[screen];

  const counts = { notif: 3 };

  if (isAuth) {
    if (screen === 'auth') return <AuthScreen onContinue={() => setScreen('onboarding')} />;
    return <Onboarding onDone={() => { setScreen('feed'); showToast('Bảng tin của bạn đã sẵn sàng!'); }} />;
  }

  if (isMobile) {
    return (
      <>
        <Topbar
          crumbs={<>Mobile preview</>}
          search={false}
          theme={theme}
          onTheme={() => setTweak({ theme: theme === 'dark' ? 'light' : 'dark' })}
        />
        <MobilePreview onBack={() => setScreen('feed')} />
        {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
      </>
    );
  }

  if (isAdmin) {
    return (
      <>
        <AdminShell
          page={adminPage}
          onNav={(p) => setAdminPage(p)}
          onExit={() => setScreen('feed')}
        >
          {adminPage === 'overview' && <AdminOverview/>}
          {adminPage === 'mod'      && <AdminModeration/>}
          {adminPage === 'rec'      && <AdminRecommendations/>}
          {adminPage === 'flagged'  && <AdminModeration/>}
          {!['overview','mod','rec','flagged'].includes(adminPage) &&
            <AdminPlaceholder page={adminPage} onJump={(p) => setAdminPage(p)} />}
        </AdminShell>
        {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
      </>
    );
  }

  return (
    <div className="app">
      <Sidebar
        active={screen === 'article' ? 'feed' : screen}
        counts={counts}
        onNav={(s) => {
          if (s === 'landing') return;
          if (s === 'notif') { setNotifOpen(o => !o); return; }
          setScreen(s);
          setOpenPost(null);
        }}
      />
      <div>
        <Topbar
          crumbs={crumbs}
          search={true}
          theme={theme}
          onTheme={() => setTweak({ theme: theme === 'dark' ? 'light' : 'dark' })}
          onAdmin={() => { setScreen('admin'); setAdminPage('overview'); }}
          onNotif={() => setNotifOpen(o => !o)}
          right={
            <button className="btn ghost sm" onClick={() => setScreen('mobile')}>
              <I.Globe size={13}/> Xem mobile
            </button>
          }
        />
        {screen === 'feed' && (
          <Feed
            onOpenPost={(p) => { setOpenPost(p); setScreen('article'); }}
            toast={showToast}
          />
        )}
        {screen === 'article' && (
          <Reader post={openPost} onBack={() => setScreen('feed')} toast={showToast} />
        )}
        {screen === 'explore' && (
          <Explore onOpenPost={(p) => { setOpenPost(p); setScreen('article'); }} />
        )}
        {screen === 'profile' && <Profile />}
        {(screen === 'saved' || screen === 'follow' || screen === 'group') && (
          <ScreenPlaceholder screen={screen} onBack={() => setScreen('feed')} />
        )}
      </div>
      <NotificationsPopover open={notifOpen} onClose={() => setNotifOpen(false)} />
      {toast && <Toast onClose={() => setToast(null)}>{toast}</Toast>}
    </div>
  );
}

function ScreenPlaceholder({ screen, onBack }) {
  const titles = {
    saved:  ['Đã lưu', 'Bộ sưu tập bài viết bạn đã lưu để đọc sau.'],
    follow: ['Đang theo dõi', 'Bài mới từ tác giả và nhóm bạn theo dõi.'],
    group:  ['Nhóm', 'Cộng đồng theo chủ đề. Đăng bài, theo dõi và tham gia thảo luận.'],
  };
  const [title, sub] = titles[screen];
  return (
    <div style={{ maxWidth: 720, margin: '60px auto', padding: '0 32px', textAlign: 'center' }}>
      <h2 className="serif" style={{ fontWeight: 500, fontSize: 32, letterSpacing: '-0.015em', margin: '0 0 8px' }}>
        {title}
      </h2>
      <p className="muted" style={{ fontSize: 15, marginBottom: 22 }}>{sub}</p>
      <div className="card card-pad" style={{ textAlign: 'left', padding: '32px 28px' }}>
        <I.Layers size={22} className="muted"/>
        <h3 className="serif" style={{ fontWeight: 500, fontSize: 20, letterSpacing: '-0.01em', margin: '12px 0 6px' }}>
          Màn hình này được phác thảo cho giai đoạn tiếp theo.
        </h3>
        <p className="muted" style={{ fontSize: 14, lineHeight: 1.55, margin: 0 }}>
          Trong bản prototype này, các flow chính tập trung ở: <b>Đăng nhập</b> → <b>Onboarding</b> → <b>Home Feed</b>,
          với khả năng xem trang chi tiết bài viết, Khám phá, Hồ sơ, Thông báo, Admin Dashboard và bản xem mobile.
          Trang <b>{title}</b> sẽ dùng layout tương tự Home Feed nhưng được lọc theo ngữ cảnh tương ứng.
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
          <button className="btn emerald sm" onClick={onBack}><I.ArrowLeft size={12}/> Trở về bảng tin</button>
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
      <div className="admin-h">
        <div>
          <h2>{t}</h2>
          <div className="sub">{s}</div>
        </div>
      </div>
      <div className="card card-pad" style={{ padding: 40, textAlign: 'center' }}>
        <I.Layers size={28} className="muted"/>
        <h3 className="serif" style={{ fontWeight: 500, fontSize: 20, margin: '12px 0 6px' }}>
          Trang này được phác thảo cho giai đoạn tiếp theo.
        </h3>
        <p className="muted" style={{ fontSize: 14, lineHeight: 1.5, maxWidth: 520, margin: '0 auto' }}>
          Trong bản prototype này, 3 trang admin trọng tâm đang hoạt động đầy đủ:
          <b> Tổng quan</b>, <b>Kiểm duyệt nội dung</b> và <b>Hiệu quả đề xuất</b>.
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'center' }}>
          <button className="btn emerald sm" onClick={() => onJump('overview')}>Mở Tổng quan</button>
          <button className="btn ghost sm" onClick={() => onJump('mod')}>Mở Kiểm duyệt</button>
          <button className="btn ghost sm" onClick={() => onJump('rec')}>Mở Hiệu quả đề xuất</button>
        </div>
      </div>
    </>
  );
}

/* ====== Tweaks panel for theme + jump-to-screen ====== */
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
          onChange={(v) => setTweak({ theme: v })}
          options={[
            { value: 'light', label: 'Sáng' },
            { value: 'dark',  label: 'Tối' },
          ]}
        />
      </TweakSection>
      <TweakSection label="Mở nhanh màn hình">
        <TweakButton label="1. Đăng nhập / Đăng ký" onClick={() => go('auth')} />
        <TweakButton label="2. Onboarding" secondary onClick={() => go('onboarding')} />
        <TweakButton label="3. Home Feed" secondary onClick={() => go('feed')} />
        <TweakButton label="4. Chi tiết bài viết" secondary onClick={() => go('article')} />
        <TweakButton label="5. Khám phá" secondary onClick={() => go('explore')} />
        <TweakButton label="6. Hồ sơ" secondary onClick={() => go('profile')} />
        <TweakButton label="7. Thông báo (popover)" secondary onClick={() => go('notif')} />
        <TweakButton label="8. Xem mobile" secondary onClick={() => go('mobile')} />
        <TweakButton label="9. Admin · Tổng quan" secondary onClick={() => go('admin')} />
        <TweakButton label="10. Admin · Kiểm duyệt" secondary onClick={() => go('admin-mod')} />
        <TweakButton label="11. Admin · Hiệu quả đề xuất" secondary onClick={() => go('admin-rec')} />
      </TweakSection>
    </TweaksPanel>
  );
}

function Root() {
  return (
    <>
      <App />
      <OcTweaks />
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<Root />);
