/* Auth + Onboarding — Tailwind */
const { useState: useStateAuthTw } = React;
const GT = window.G;
const IT = window.I;

function AuthScreen({ onContinue }) {
  const [mode, setMode] = useStateAuthTw('register');
  const [email, setEmail] = useStateAuthTw('');
  const [pwd, setPwd] = useStateAuthTw('');
  const [name, setName] = useStateAuthTw('');
  const [loading, setLoading] = useStateAuthTw(false);
  const [err, setErr] = useStateAuthTw(null);
  const [success, setSuccess] = useStateAuthTw(false);

  const submit = () => {
    setErr(null);
    if (!email || !email.includes('@')) { setErr({ f: 'email', m: 'Email chưa hợp lệ.' }); return; }
    if (pwd.length < 6) { setErr({ f: 'pwd', m: 'Mật khẩu cần ít nhất 6 ký tự.' }); return; }
    setLoading(true);
    setTimeout(() => { setLoading(false); setSuccess(true); setTimeout(onContinue, 700); }, 900);
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2" data-screen-label="02 Auth">
      {/* Left: brand art */}
      <aside className="hidden md:flex flex-col p-12 relative overflow-hidden bg-gradient-to-br from-[#081610] to-[#0c1f17] text-white">
        <div className="absolute -right-32 -top-32 w-[480px] h-[480px] rounded-full border border-white/8"/>
        <div className="absolute -right-12 top-16 w-[280px] h-[280px] rounded-full border border-white/12"/>
        <div className="absolute right-16 top-44 w-[120px] h-[120px] rounded-full bg-emerald-grad shadow-[0_20px_60px_-10px_rgba(0,200,130,0.6)]"/>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-[10px] bg-emerald-grad grid place-items-center text-white font-serif italic font-semibold text-[19px] shadow-glow-emerald">O</div>
          <div className="font-serif text-[19px] tracking-tight">Oecophy<em className="not-italic text-emerald-400">lla</em></div>
        </div>
        <h1 className="mt-auto font-serif text-[48px] leading-[1.05] tracking-[-0.025em] font-medium max-w-[460px]">
          Theo dõi tin tức phù hợp với bạn, mỗi ngày.
        </h1>
        <div className="mt-4 text-[13px] text-white/55 max-w-md">
          Một mạng xã hội nội dung minh bạch, có kiểm duyệt và do bạn tự định hình.
        </div>
      </aside>

      {/* Right: form */}
      <div className="flex flex-col justify-center p-10 sm:p-14 max-w-[520px] w-full mx-auto">
        <div className={`${GT.tabs} self-start mb-7`}>
          <button onClick={() => setMode('login')}    className={`${GT.tab} ${mode === 'login' ? GT.tabActive : ''}`}>Đăng nhập</button>
          <button onClick={() => setMode('register')} className={`${GT.tab} ${mode === 'register' ? GT.tabActive : ''}`}>Tạo tài khoản</button>
        </div>

        <h2 className="font-serif text-[28px] font-medium tracking-tight">
          {mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản Oecophylla'}
        </h2>
        <p className="text-[14px] text-muted dark:text-white/60 mt-1.5 mb-7">
          {mode === 'login' ? 'Tiếp tục với bảng tin đã cá nhân hóa của bạn.' : 'Chỉ mất 1 phút. Tiếp theo bạn sẽ chọn các chủ đề mình quan tâm.'}
        </p>

        <div className="grid grid-cols-3 gap-2.5 mb-5">
          {[
            { n: 'Google',    svg: <svg width="16" height="16" viewBox="0 0 24 24"><path d="M22 12c0-.8-.07-1.5-.2-2.2H12v4.2h5.6c-.24 1.3-.97 2.4-2.06 3.13v2.6h3.3c1.93-1.78 3.04-4.4 3.04-7.5z" fill="#4285F4"/><path d="M12 22c2.7 0 5-.9 6.66-2.4l-3.3-2.55c-.9.6-2.05.97-3.36.97-2.6 0-4.8-1.75-5.58-4.1H3.04v2.6A10 10 0 0012 22z" fill="#34A853"/><path d="M6.42 13.92A6 6 0 016.1 12c0-.66.12-1.3.32-1.92V7.48H3.04A10 10 0 002 12c0 1.6.38 3.1 1.04 4.52l3.38-2.6z" fill="#FBBC05"/><path d="M12 5.97c1.47 0 2.78.5 3.82 1.5l2.86-2.87C16.97 3 14.66 2 12 2A10 10 0 003.04 7.48l3.38 2.6C7.2 7.74 9.4 5.97 12 5.97z" fill="#EA4335"/></svg> },
            { n: 'Facebook',  svg: <svg width="16" height="16" viewBox="0 0 24 24" fill="#1877F2"><path d="M22 12a10 10 0 10-11.6 9.9V14.9H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.5h-1.3c-1.2 0-1.6.8-1.6 1.6V12h2.8l-.4 2.9h-2.3v7A10 10 0 0022 12z"/></svg> },
            { n: 'Apple',     svg: <svg width="16" height="16" viewBox="0 0 24 24"><path d="M16.4 3c-1.06.07-2.3.74-3.04 1.6-.66.78-1.22 1.95-1 3.09 1.16.04 2.34-.65 3.04-1.5.65-.8 1.15-1.95 1-3.19zM20 18c-.5 1.13-.74 1.62-1.4 2.6-.9 1.4-2.18 3.13-3.78 3.15-1.4 0-1.77-.93-3.7-.93-1.92 0-2.32.94-3.73.94-1.6-.02-2.81-1.6-3.7-3-2.5-3.94-2.78-8.56-1.23-11.02 1.1-1.75 2.84-2.77 4.48-2.77 1.67 0 2.72.92 4.1.92 1.34 0 2.16-.92 4.1-.92 1.46 0 3 .8 4.1 2.2-3.6 1.95-3 7.1.76 8.83z" fill="currentColor"/></svg> },
          ].map(s => (
            <button key={s.n} className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-2xl bg-white/55 dark:bg-white/6 border border-white/60 dark:border-white/10 backdrop-blur-md text-[13px] font-medium hover:bg-white/75 transition-colors">
              {s.svg} {s.n}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3.5 my-5 text-[12px] text-muted dark:text-white/50">
          <div className="flex-1 h-px bg-ink/10 dark:bg-white/10"/>
          hoặc dùng email
          <div className="flex-1 h-px bg-ink/10 dark:bg-white/10"/>
        </div>

        {mode === 'register' && (
          <Field label="Tên hiển thị">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Nguyễn Văn A" className={GT.input}/>
          </Field>
        )}
        <Field label="Email" error={err?.f === 'email' ? err.m : null}>
          <input value={email} onChange={e => setEmail(e.target.value)} type="email" placeholder="ban@vidu.com" className={`${GT.input} ${err?.f === 'email' ? 'border-rose-500/60 bg-rose-50/40' : ''}`}/>
        </Field>
        <Field label="Mật khẩu" error={err?.f === 'pwd' ? err.m : null}
               hint={err?.f === 'pwd' ? null : 'Dùng cụm từ dễ nhớ thay vì mật khẩu khó.'}>
          <input value={pwd} onChange={e => setPwd(e.target.value)} type="password" placeholder="Tối thiểu 6 ký tự" className={`${GT.input} ${err?.f === 'pwd' ? 'border-rose-500/60 bg-rose-50/40' : ''}`}/>
        </Field>

        {mode === 'login' && (
          <div className="flex items-center justify-between mb-3 -mt-1">
            <label className="flex items-center gap-2 text-[13px] text-ink-2 dark:text-white/70">
              <input type="checkbox" defaultChecked className="accent-emerald-500"/> Ghi nhớ thiết bị này
            </label>
            <a href="#" className="text-[13px] font-semibold text-emerald-700 dark:text-emerald-400">Quên mật khẩu?</a>
          </div>
        )}

        <button onClick={submit} disabled={loading || success}
          className={`${GT.btn} ${GT.btnEmerald} ${GT.btnLg} w-full mt-3 disabled:opacity-80`}>
          {loading && <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full oc-spin"/>}
          {success && <IT.Check size={16}/>}
          {!loading && !success && (mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản và tiếp tục')}
          {loading && 'Đang xử lý…'}
          {success && 'Thành công, đang chuyển hướng…'}
        </button>

        <p className="text-[12px] text-muted dark:text-white/50 text-center mt-4 leading-relaxed">
          Khi tiếp tục, bạn đồng ý với <a href="#" className="underline">Điều khoản</a> và <a href="#" className="underline">Chính sách bảo mật</a> của Oecophylla.
        </p>
      </div>
    </div>
  );
}

function Field({ label, hint, error, children }) {
  return (
    <div className="flex flex-col gap-1.5 mb-3.5">
      <label className="text-[12px] font-semibold text-ink-2 dark:text-white/80">{label}</label>
      {children}
      {error && <span className="text-[12px] text-rose-600 dark:text-rose-400 flex items-center gap-1"><IT.AlertCircle size={12}/> {error}</span>}
      {hint && !error && <span className="text-[12px] text-muted dark:text-white/55">{hint}</span>}
    </div>
  );
}

function Onboarding({ onDone }) {
  const [selected, setSelected] = useStateAuthTw(new Set(['ai', 'tech', 'sci']));
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };
  const min = 3;
  const ok = selected.size >= min;
  const progress = Math.min(100, 40 + (selected.size / 8) * 60);

  return (
    <div className="min-h-screen flex flex-col" data-screen-label="03 Onboarding">
      <header className={`sticky top-0 z-10 px-8 py-4 flex items-center gap-4 border-b border-white/40 dark:border-white/8 ${GT.glassBar}`}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-[10px] bg-emerald-grad grid place-items-center text-white font-serif italic font-semibold text-[19px] shadow-glow-emerald">O</div>
          <div className="font-serif text-[19px] tracking-tight">Oecophy<em className="not-italic text-emerald-500">lla</em></div>
        </div>
        <div className="flex-1 max-w-[360px] mx-8">
          <div className="flex justify-between text-[12px] text-muted dark:text-white/55 mb-1.5">
            <span>Bước 2 / 3 · Chủ đề quan tâm</span>
            <span><b className="text-ink dark:text-white">{selected.size}</b> đã chọn</span>
          </div>
          <div className="h-1.5 rounded-full bg-ink/8 dark:bg-white/10 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-[#00C480] to-[#008A57] rounded-full transition-[width] duration-500 shadow-[0_0_12px_rgba(0,200,130,0.5)]" style={{ width: progress + '%' }}/>
          </div>
        </div>
        <button className={`${GT.btn} ${GT.btnGhost} ${GT.btnSm}`}>Bỏ qua</button>
      </header>

      <div className="flex-1 max-w-[920px] mx-auto w-full px-8 py-16">
        <h1 className="font-serif text-[40px] leading-[1.1] tracking-[-0.022em] font-medium text-center mb-3">
          Bạn muốn đọc về điều gì?
        </h1>
        <p className="text-[15px] text-muted dark:text-white/65 text-center max-w-[560px] mx-auto leading-relaxed mb-10">
          Oecophylla sẽ dùng các lựa chọn này để khởi tạo news feed cá nhân hóa cho bạn.
          Bạn có thể thay đổi bất cứ lúc nào trong trang Hồ sơ. Chọn ít nhất {min} chủ đề.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {window.DATA.TOPICS.map(t => {
            const Ic = IT[t.icon] || IT.Sparkle;
            const isSel = selected.has(t.id);
            return (
              <button key={t.id} onClick={() => toggle(t.id)}
                className={`relative text-left flex items-center gap-3.5 p-4 rounded-3xl transition-all duration-200 hover:-translate-y-0.5
                  ${isSel
                    ? 'bg-gradient-to-br from-emerald-500/25 to-blue-400/15 border border-emerald-500/40 shadow-[0_16px_40px_-10px_rgba(0,170,100,0.35)]'
                    : 'bg-white/55 dark:bg-white/6 backdrop-blur-2xl border border-white/60 dark:border-white/10 shadow-glass shadow-glass-inner hover:shadow-glass-lg'}`}>
                <div className={`w-10 h-10 rounded-xl grid place-items-center flex-none transition-colors
                  ${isSel
                    ? 'bg-emerald-grad text-white shadow-glow-emerald'
                    : 'bg-white/60 dark:bg-white/8 backdrop-blur-md border border-white/60 dark:border-white/10 text-ink-2 dark:text-white/80'}`}>
                  <Ic size={20}/>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[14px]">{t.name}</div>
                  <div className="text-[11.5px] text-muted dark:text-white/55 mt-0.5">{t.desc}</div>
                </div>
                <div className={`absolute top-3 right-3 w-[18px] h-[18px] rounded-full bg-emerald-grad text-white grid place-items-center shadow-[0_4px_10px_-2px_rgba(0,170,100,0.5)] transition-opacity ${isSel ? 'opacity-100' : 'opacity-0'}`}>
                  <IT.Check size={11} sw={2.5}/>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-8 flex items-start gap-3.5 p-5 rounded-3xl bg-gradient-to-br from-emerald-500/16 to-blue-400/10 border border-white/60 dark:border-white/10 backdrop-blur-2xl shadow-glass shadow-glass-inner">
          <IT.Shield size={18} className="text-emerald-700 dark:text-emerald-300 mt-0.5 flex-none"/>
          <div>
            <div className="font-semibold text-[14px] mb-1">Bạn vẫn kiểm soát bảng tin của mình</div>
            <div className="text-[13px] text-ink-2 dark:text-white/75 leading-relaxed">
              Cá nhân hóa của Oecophylla minh bạch: mỗi bài viết đều có dòng giải thích "được đề xuất vì sao".
              Bạn có thể tắt cá nhân hóa, ẩn chủ đề không muốn xem, hoặc chuyển sang chế độ thời gian thực bất cứ lúc nào.
            </div>
          </div>
        </div>
      </div>

      <footer className={`sticky bottom-0 z-10 px-8 py-3.5 flex items-center gap-4 border-t border-white/40 dark:border-white/8 ${GT.glassBar}`}>
        <div className="text-[13px] text-muted dark:text-white/60">
          {ok
            ? <><IT.Check size={14} className="inline -mt-0.5 text-emerald-500"/> Đủ điều kiện tiếp tục.</>
            : `Cần chọn thêm ${min - selected.size} chủ đề.`}
        </div>
        <div className="ml-auto flex gap-2.5">
          <button className={`${GT.btn} ${GT.btnGhost}`}>Quay lại</button>
          <button onClick={onDone} disabled={!ok}
            className={`${GT.btn} ${GT.btnEmerald} ${GT.btnLg} disabled:opacity-50`}>
            Xây dựng bảng tin của tôi <IT.ArrowRight size={14}/>
          </button>
        </div>
      </footer>
    </div>
  );
}

Object.assign(window, { AuthScreen, Onboarding });
