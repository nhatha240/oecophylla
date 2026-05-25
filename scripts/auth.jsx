/* Auth + Onboarding screens */
const { useState: useStateAuth } = React;

function AuthScreen({ onContinue }) {
  const [mode, setMode] = useStateAuth('register');
  const [email, setEmail] = useStateAuth('');
  const [pwd, setPwd] = useStateAuth('');
  const [name, setName] = useStateAuth('');
  const [loading, setLoading] = useStateAuth(false);
  const [err, setErr] = useStateAuth(null);
  const [success, setSuccess] = useStateAuth(false);

  const submit = () => {
    setErr(null);
    if (!email || !email.includes('@')) { setErr({ field: 'email', msg: 'Email chưa hợp lệ.' }); return; }
    if (pwd.length < 6) { setErr({ field: 'pwd', msg: 'Mật khẩu cần ít nhất 6 ký tự.' }); return; }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSuccess(true);
      setTimeout(onContinue, 700);
    }, 900);
  };

  return (
    <div className="auth-page" data-screen-label="02 Auth">
      <aside className="auth-art">
        <div className="brand">
          <div className="brand-mark">O</div>
          <div className="brand-name">Oecophy<em>lla</em></div>
        </div>
        <div className="deco"></div>
        <div className="deco-2"></div>
        <div className="deco-3"></div>
        <h1 className="serif">Theo dõi tin tức phù hợp với bạn, mỗi ngày.</h1>
        <div className="quote-author">Một mạng xã hội nội dung minh bạch, có kiểm duyệt và do bạn tự định hình.</div>
      </aside>

      <div className="auth-form-wrap">
        <div className="auth-tabs">
          <button className={`auth-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>Đăng nhập</button>
          <button className={`auth-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => setMode('register')}>Tạo tài khoản</button>
        </div>

        <h2 className="serif" style={{ margin: '0 0 6px', fontWeight: 500, fontSize: 28, letterSpacing: '-0.015em' }}>
          {mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản Oecophylla'}
        </h2>
        <p className="muted" style={{ marginTop: 0, marginBottom: 28, fontSize: 14 }}>
          {mode === 'login' ? 'Tiếp tục với bảng tin đã cá nhân hóa của bạn.' : 'Chỉ mất 1 phút. Tiếp theo bạn sẽ chọn các chủ đề mình quan tâm.'}
        </p>

        <div className="social-row">
          <button className="social-btn"><svg width="16" height="16" viewBox="0 0 24 24"><path d="M22 12c0-.8-.07-1.5-.2-2.2H12v4.2h5.6c-.24 1.3-.97 2.4-2.06 3.13v2.6h3.3c1.93-1.78 3.04-4.4 3.04-7.5z" fill="#4285F4"/><path d="M12 22c2.7 0 5-.9 6.66-2.4l-3.3-2.55c-.9.6-2.05.97-3.36.97-2.6 0-4.8-1.75-5.58-4.1H3.04v2.6A10 10 0 0012 22z" fill="#34A853"/><path d="M6.42 13.92A6 6 0 016.1 12c0-.66.12-1.3.32-1.92V7.48H3.04A10 10 0 002 12c0 1.6.38 3.1 1.04 4.52l3.38-2.6z" fill="#FBBC05"/><path d="M12 5.97c1.47 0 2.78.5 3.82 1.5l2.86-2.87C16.97 3 14.66 2 12 2A10 10 0 003.04 7.48l3.38 2.6C7.2 7.74 9.4 5.97 12 5.97z" fill="#EA4335"/></svg> Google</button>
          <button className="social-btn"><svg width="16" height="16" viewBox="0 0 24 24" fill="#1877F2"><path d="M22 12a10 10 0 10-11.6 9.9V14.9H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.5h-1.3c-1.2 0-1.6.8-1.6 1.6V12h2.8l-.4 2.9h-2.3v7A10 10 0 0022 12z"/></svg> Facebook</button>
          <button className="social-btn"><svg width="16" height="16" viewBox="0 0 24 24"><path d="M16.4 3c-1.06.07-2.3.74-3.04 1.6-.66.78-1.22 1.95-1 3.09 1.16.04 2.34-.65 3.04-1.5.65-.8 1.15-1.95 1-3.19zM20 18c-.5 1.13-.74 1.62-1.4 2.6-.9 1.4-2.18 3.13-3.78 3.15-1.4 0-1.77-.93-3.7-.93-1.92 0-2.32.94-3.73.94-1.6-.02-2.81-1.6-3.7-3-2.5-3.94-2.78-8.56-1.23-11.02 1.1-1.75 2.84-2.77 4.48-2.77 1.67 0 2.72.92 4.1.92 1.34 0 2.16-.92 4.1-.92 1.46 0 3 .8 4.1 2.2-3.6 1.95-3 7.1.76 8.83z" fill="currentColor"/></svg> Apple</button>
        </div>

        <div className="divider-or">hoặc dùng email</div>

        {mode === 'register' && (
          <div className="field">
            <label>Tên hiển thị</label>
            <input className="input" placeholder="Nguyễn Văn A" value={name} onChange={e => setName(e.target.value)} />
          </div>
        )}

        <div className={`field ${err?.field === 'email' ? 'err' : ''}`}>
          <label>Email</label>
          <input className="input" type="email" placeholder="ban@vidu.com" value={email} onChange={e => setEmail(e.target.value)} />
          {err?.field === 'email' && <span className="err-msg"><I.AlertCircle size={12}/> {err.msg}</span>}
        </div>

        <div className={`field ${err?.field === 'pwd' ? 'err' : ''}`}>
          <label>Mật khẩu</label>
          <input className="input" type="password" placeholder="Tối thiểu 6 ký tự" value={pwd} onChange={e => setPwd(e.target.value)} />
          {err?.field === 'pwd'
            ? <span className="err-msg"><I.AlertCircle size={12}/> {err.msg}</span>
            : <span className="hint">Dùng cụm từ dễ nhớ thay vì mật khẩu khó.</span>
          }
        </div>

        {mode === 'login' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <label style={{ fontSize: 13, color: 'var(--ink-2)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" defaultChecked /> Ghi nhớ thiết bị này
            </label>
            <a href="#" style={{ fontSize: 13, color: 'var(--emerald-700)', fontWeight: 600 }}>Quên mật khẩu?</a>
          </div>
        )}

        <button className="btn emerald lg" style={{ width: '100%', marginTop: 8 }} onClick={submit} disabled={loading || success}>
          {loading && <span className="loader" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .8s linear infinite' }}/>}
          {success && <I.Check size={16}/>}
          {!loading && !success && (mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản và tiếp tục')}
          {loading && 'Đang xử lý…'}
          {success && 'Thành công, đang chuyển hướng…'}
        </button>

        <p className="muted" style={{ fontSize: 12, textAlign: 'center', marginTop: 16, lineHeight: 1.5 }}>
          Khi tiếp tục, bạn đồng ý với <a href="#" style={{ textDecoration: 'underline' }}>Điều khoản</a> và <a href="#" style={{ textDecoration: 'underline' }}>Chính sách bảo mật</a> của Oecophylla.
        </p>

        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

function Onboarding({ onDone }) {
  const [selected, setSelected] = useStateAuth(new Set(['ai', 'tech', 'sci']));
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };
  const min = 3;
  const ok = selected.size >= min;
  const progress = Math.min(100, 40 + (selected.size / 8) * 60);

  return (
    <div className="onboarding" data-screen-label="03 Onboarding">
      <header className="onb-head">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark">O</div>
          <div className="brand-name">Oecophy<em>lla</em></div>
        </div>
        <div className="onb-progress">
          <div className="onb-progress-meta">
            <span>Bước 2 / 3 · Chủ đề quan tâm</span>
            <span><b>{selected.size}</b> đã chọn</span>
          </div>
          <div className="onb-progress-track">
            <div className="onb-progress-fill" style={{ width: progress + '%' }} />
          </div>
        </div>
        <button className="btn ghost sm">Bỏ qua</button>
      </header>

      <div className="onb-body">
        <h1 className="onb-title">Bạn muốn đọc về điều gì?</h1>
        <p className="onb-sub">
          Oecophylla sẽ dùng các lựa chọn này để khởi tạo news feed cá nhân hóa cho bạn.
          Bạn có thể thay đổi bất cứ lúc nào trong trang Hồ sơ. Chọn ít nhất {min} chủ đề.
        </p>

        <div className="topic-grid">
          {window.DATA.TOPICS.map(t => {
            const Ic = I[t.icon] || I.Sparkle;
            const isSel = selected.has(t.id);
            return (
              <button key={t.id}
                className={`topic-card ${isSel ? 'selected' : ''}`}
                onClick={() => toggle(t.id)}>
                <div className="topic-icon"><Ic size={20}/></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="topic-name">{t.name}</div>
                  <div className="topic-desc">{t.desc}</div>
                </div>
                <div className="topic-check"><I.Check size={11}/></div>
              </button>
            );
          })}
        </div>

        <div className="card" style={{ marginTop: 32, padding: '18px 22px', display: 'flex', gap: 14, alignItems: 'flex-start', background: 'var(--emerald-50)', borderColor: 'var(--emerald-100)' }}>
          <I.Shield size={18} style={{ color: 'var(--emerald-700)', marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Bạn vẫn kiểm soát bảng tin của mình</div>
            <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.5 }}>
              Cá nhân hóa của Oecophylla minh bạch: mỗi bài viết đều có dòng giải thích “được đề xuất vì sao”.
              Bạn có thể tắt cá nhân hóa, ẩn chủ đề không muốn xem, hoặc chuyển sang chế độ thời gian thực bất cứ lúc nào.
            </div>
          </div>
        </div>
      </div>

      <footer className="onb-foot">
        <div className="left">
          {ok ? <><I.Check size={14} style={{ color: 'var(--emerald-500)', verticalAlign: -2 }}/> Đủ điều kiện tiếp tục.</> : `Cần chọn thêm ${min - selected.size} chủ đề.`}
        </div>
        <div className="right">
          <button className="btn ghost">Quay lại</button>
          <button className="btn emerald lg" disabled={!ok} onClick={onDone}>
            Xây dựng bảng tin của tôi <I.ArrowRight size={14}/>
          </button>
        </div>
      </footer>
    </div>
  );
}

Object.assign(window, { AuthScreen, Onboarding });
