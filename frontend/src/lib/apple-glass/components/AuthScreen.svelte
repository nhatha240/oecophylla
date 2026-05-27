<script lang="ts">
  import Icon from './Icon.svelte';

  export let onContinue: () => void = () => {};

  let mode: 'login' | 'register' = 'register';
  let email = '';
  let pwd = '';
  let name = '';
  let loading = false;
  let success = false;
  let err: { field: 'email' | 'pwd'; msg: string } | null = null;

  function submit() {
    err = null;
    if (!email || !email.includes('@')) {
      err = { field: 'email', msg: 'Email chưa hợp lệ.' };
      return;
    }
    if (pwd.length < 6) {
      err = { field: 'pwd', msg: 'Mật khẩu cần ít nhất 6 ký tự.' };
      return;
    }
    loading = true;
    window.setTimeout(() => {
      loading = false;
      success = true;
      window.setTimeout(onContinue, 700);
    }, 900);
  }
</script>

<div class="auth-page" data-screen-label="02 Auth">
  <aside class="auth-art">
    <div class="brand"><div class="brand-mark">O</div><div class="brand-name">Oecophy<em>lla</em></div></div>
    <div class="deco"></div><div class="deco-2"></div><div class="deco-3"></div>
    <h1 class="serif">Theo dõi tin tức phù hợp với bạn, mỗi ngày.</h1>
    <div class="quote-author">Một mạng xã hội nội dung minh bạch, có kiểm duyệt và do bạn tự định hình.</div>
  </aside>

  <div class="auth-form-wrap">
    <div class="auth-tabs">
      <button class={`auth-tab ${mode === 'login' ? 'active' : ''}`} on:click={() => (mode = 'login')}>Đăng nhập</button>
      <button class={`auth-tab ${mode === 'register' ? 'active' : ''}`} on:click={() => (mode = 'register')}>Tạo tài khoản</button>
    </div>
    <h2 class="serif auth-title">{mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản Oecophylla'}</h2>
    <p class="muted auth-sub">{mode === 'login' ? 'Tiếp tục với bảng tin đã cá nhân hóa của bạn.' : 'Chỉ mất 1 phút. Tiếp theo bạn sẽ chọn các chủ đề mình quan tâm.'}</p>

    <div class="social-row">
      <button class="social-btn">Google</button>
      <button class="social-btn">Facebook</button>
      <button class="social-btn">Apple</button>
    </div>
    <div class="divider-or">hoặc dùng email</div>

    {#if mode === 'register'}
      <div class="field"><label for="display-name">Tên hiển thị</label><input id="display-name" class="input" placeholder="Nguyễn Văn A" bind:value={name} /></div>
    {/if}
    <div class={`field ${err?.field === 'email' ? 'err' : ''}`}>
      <label for="auth-email">Email</label>
      <input id="auth-email" class="input" type="email" placeholder="ban@vidu.com" bind:value={email} />
      {#if err?.field === 'email'}<span class="err-msg"><Icon name="AlertCircle" size={12} /> {err.msg}</span>{/if}
    </div>
    <div class={`field ${err?.field === 'pwd' ? 'err' : ''}`}>
      <label for="auth-password">Mật khẩu</label>
      <input id="auth-password" class="input" type="password" placeholder="Tối thiểu 6 ký tự" bind:value={pwd} />
      {#if err?.field === 'pwd'}<span class="err-msg"><Icon name="AlertCircle" size={12} /> {err.msg}</span>{:else}<span class="hint">Dùng cụm từ dễ nhớ thay vì mật khẩu khó.</span>{/if}
    </div>
    {#if mode === 'login'}
      <div class="remember-row"><label><input type="checkbox" checked /> Ghi nhớ thiết bị này</label><a href="/">Quên mật khẩu?</a></div>
    {/if}
    <button class="btn emerald lg" style="width: 100%; margin-top: 8px" on:click={submit} disabled={loading || success}>
      {#if success}<Icon name="Check" size={16} />{/if}
      {loading ? 'Đang xử lý…' : success ? 'Thành công, đang chuyển hướng…' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản và tiếp tục'}
    </button>
    <p class="muted terms">Khi tiếp tục, bạn đồng ý với <a href="/">Điều khoản</a> và <a href="/">Chính sách bảo mật</a> của Oecophylla.</p>
  </div>
</div>

<style>
  .auth-title { margin: 0 0 6px; font-weight: 500; font-size: 28px; letter-spacing: -0.015em; }
  .auth-sub { margin-top: 0; margin-bottom: 28px; font-size: 14px; }
  .remember-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 13px; }
  .remember-row label { color: var(--ink-2); display: flex; align-items: center; gap: 6px; }
  .remember-row a { color: var(--emerald-700); font-weight: 600; }
  .terms { font-size: 12px; text-align: center; margin-top: 16px; line-height: 1.5; }
  .terms a { text-decoration: underline; }
</style>
