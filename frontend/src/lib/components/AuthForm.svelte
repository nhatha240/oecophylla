<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let mode: 'login' | 'register';
  export let error: string | null = null;
</script>

<div class="auth-page" data-screen-label="02 Auth">
  <aside class="auth-art">
    <div class="brand">
      <div class="brand-mark">O</div>
      <div class="brand-name">Oecophy<em>lla</em></div>
    </div>
    <div class="deco"></div>
    <div class="deco-2"></div>
    <div class="deco-3"></div>
    <h1 class="serif">Theo dõi tin tức phù hợp với bạn, mỗi ngày.</h1>
    <div class="quote-author">Một mạng xã hội nội dung minh bạch, có kiểm duyệt và do bạn tự định hình.</div>
  </aside>

  <div class="auth-form-wrap">
    <div class="auth-tabs">
      <a class:active={mode === 'login'} class="auth-tab" href="/login">Đăng nhập</a>
      <a class:active={mode === 'register'} class="auth-tab" href="/register">Tạo tài khoản</a>
    </div>

    <h1 class="serif auth-title">{mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản Oecophylla'}</h1>
    <p class="muted auth-sub">
      {mode === 'login'
        ? 'Tiếp tục với bảng tin đã cá nhân hoá của bạn.'
        : 'Chỉ mất 1 phút. Sau đó bạn có thể bắt đầu đọc, viết và theo dõi các chủ đề mình quan tâm.'}
    </p>

    <div class="social-row">
      <button class="social-btn" type="button">Google</button>
      <button class="social-btn" type="button">Facebook</button>
      <button class="social-btn" type="button">Apple</button>
    </div>
    <div class="divider-or">hoặc dùng email</div>

    <form method="post">
      {#if mode === 'register'}
        <div class="field">
          <label for="username">Username</label>
          <input id="username" class="input" name="username" placeholder="quynhanh" required />
        </div>
        <div class="field">
          <label for="display_name">Tên hiển thị</label>
          <input id="display_name" class="input" name="display_name" placeholder="Nguyễn Quỳnh Anh" />
        </div>
      {/if}

      <div class:err={!!error} class="field">
        <label for="email_or_username">{mode === 'login' ? 'Email hoặc username' : 'Email'}</label>
        <input
          id="email_or_username"
          class="input"
          type={mode === 'login' ? 'text' : 'email'}
          name={mode === 'login' ? 'email_or_username' : 'email'}
          placeholder={mode === 'login' ? 'ban@vidu.com hoặc username' : 'ban@vidu.com'}
          required
        />
      </div>

      <div class:err={!!error} class="field">
        <label for="password">Mật khẩu</label>
        <input id="password" class="input" type="password" name="password" placeholder="Tối thiểu 8 ký tự" required />
        {#if error}
          <span class="err-msg"><Icon name="AlertCircle" size={12} /> {error}</span>
        {:else if mode === 'login'}
          <span class="hint">Cookie phiên sẽ được lưu an toàn trên trình duyệt.</span>
        {:else}
          <span class="hint">Dùng một cụm từ dễ nhớ thay vì mật khẩu khó đọc.</span>
        {/if}
      </div>

      {#if mode === 'login'}
        <div class="remember-row">
          <label><input type="checkbox" checked /> Ghi nhớ thiết bị này</label>
          <a href="/register">Chưa có tài khoản?</a>
        </div>
      {/if}

      <button class="btn emerald lg auth-submit" type="submit">
        {mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản và tiếp tục'}
      </button>
    </form>

    <p class="muted terms">
      Khi tiếp tục, bạn đồng ý với <a href="/">Điều khoản</a> và <a href="/">Chính sách bảo mật</a> của Oecophylla.
    </p>
  </div>
</div>

<style>
  .auth-title {
    margin: 0 0 6px;
    font-weight: 500;
    font-size: 28px;
    letter-spacing: -0.015em;
  }
  .auth-sub {
    margin-top: 0;
    margin-bottom: 28px;
    font-size: 14px;
  }
  .auth-submit {
    width: 100%;
    margin-top: 8px;
  }
  .remember-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-size: 13px;
  }
  .remember-row label {
    color: var(--ink-2);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .remember-row a {
    color: var(--emerald-700);
    font-weight: 600;
  }
  .terms {
    font-size: 12px;
    text-align: center;
    margin-top: 16px;
    line-height: 1.5;
  }
  .terms a {
    text-decoration: underline;
  }
</style>
