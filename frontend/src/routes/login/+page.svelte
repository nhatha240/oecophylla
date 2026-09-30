<script lang="ts">
  import Logo from '$lib/components/Logo.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let form: { error?: string; email_or_username?: string } | null = null;
  let showPassword = false;
</script>

<svelte:head>
  <title>Đăng nhập — Oecophylla</title>
  <meta name="description" content="Đăng nhập vào Oecophylla để đọc tin và tham gia những cuộc thảo luận có chiều sâu." />
</svelte:head>

<div class="auth-backdrop">
  <div class="auth-frame">
    <header class="auth-header">
      <a href="/" aria-label="Trang chủ Oecophylla"><Logo size={39} /></a>
      <span class="brand-divider"></span>
      <span class="tagline">Tin cậy hơn. Cùng suy nghĩ xa hơn.</span>
      <span class="auth-header-right">Vì một cộng đồng thông thái hơn <span>—</span> VI⌄</span>
    </header>

    <main class="auth-content">
      <section class="auth-story" aria-label="Giới thiệu Oecophylla">
        <div class="story-copy">
          <p class="eyebrow">TIN TỨC &nbsp;·&nbsp; THẢO LUẬN &nbsp;·&nbsp; CON NGƯỜI &nbsp;·&nbsp; TƯƠNG LAI</p>
          <h1>Hiểu sâu hơn<br />về thế giới,<br />cùng nhau kiến tạo<br />những đối thoại tốt đẹp hơn.</h1>
          <p>Oecophylla là nền tảng tin tức cá nhân hóa của người Việt, ưu tiên nội dung đáng tin cậy, thảo luận có chiều sâu và minh bạch trong gợi ý từ AI.</p>
        </div>
        <p class="image-caption">Những góc nhìn tử tế<br />cũng có thể tạo nên thay đổi lớn.</p>
      </section>

      <section class="auth-panel" aria-labelledby="login-title">
        <p class="eyebrow">CHÀO MỪNG BẠN ĐẾN VỚI</p>
        <h2 id="login-title">Oecophylla</h2>
        <p class="panel-intro">Tin tức đáng tin cậy. Những cuộc thảo luận có chiều sâu.<br />Và một cộng đồng luôn hướng đến điều tốt đẹp hơn.</p>

        <form method="POST" class="auth-form">
          <label for="email_or_username">Email hoặc tên người dùng</label>
          <div class="input-wrap"><Icon name="User" size={18} /><input id="email_or_username" name="email_or_username" type="text" autocomplete="username" value={form?.email_or_username ?? ''} placeholder="Nhập email hoặc tên người dùng" maxlength="254" required /></div>
          <label for="password">Mật khẩu</label>
          <div class="input-wrap"><Icon name="Shield" size={18} /><input id="password" name="password" type={showPassword ? 'text' : 'password'} autocomplete="current-password" placeholder="Nhập mật khẩu" maxlength="256" required /><button type="button" class="toggle-password" on:click={() => showPassword = !showPassword} aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}><Icon name={showPassword ? 'EyeOff' : 'Eye'} size={17} /></button></div>
          {#if form?.error}<p class="form-error" role="alert">{form.error}</p>{/if}
          <button class="submit" type="submit">Đăng nhập <Icon name="ArrowRight" size={18} /></button>
        </form>

        <div class="or"><span>hoặc</span></div>
        <a class="register-link" href="/register">Đăng ký tài khoản</a>

        <div class="values">
          <div><Icon name="Shield" size={25} /><strong>Nội dung đáng tin cậy</strong><span>Được kiểm chứng và ưu tiên từ các nguồn uy tín.</span></div>
          <div><Icon name="Sparkle" size={25} /><strong>Minh bạch AI</strong><span>Hiển thị lý do gợi ý để bạn làm chủ trải nghiệm.</span></div>
          <div><Icon name="Users" size={25} /><strong>Cộng đồng văn minh</strong><span>Thảo luận có chiều sâu, tôn trọng khác biệt.</span></div>
        </div>
        <p class="auth-footnote">Những thông tin tốt đẹp luôn tìm được người xứng đáng. — Oecophylla</p>
      </section>
    </main>
  </div>
</div>

<style>
  .auth-backdrop { height: 100vh; height: 100dvh; display: grid; place-items: center; overflow: hidden; padding: 0; background: #fff; }
  .auth-frame { display: grid; grid-template-rows: clamp(58px, 8vh, 78px) minmax(0, 1fr); width: 100%; height: 100%; min-height: 0; overflow: hidden; border: 0; border-radius: 0; background: #fdfdfc; box-shadow: none; }
  .auth-header { min-width: 0; display: flex; align-items: center; gap: 26px; padding: 0 54px; }
  .auth-header a { display: inline-flex; }
  .brand-divider { width: 1px; height: 24px; background: #9aaaa5; }
  .tagline, .auth-header-right { font: 12px 'Lora', Georgia, serif; color: #415c56; }
  .auth-header-right { margin-left: auto; }
  .auth-header-right span { margin: 0 22px; }
  .auth-content { min-height: 0; min-width: 0; display: grid; grid-template-columns: minmax(0, 56%) minmax(0, 44%); }
  .auth-story { position: relative; min-width: 0; min-height: 0; display: flex; flex-direction: column; justify-content: space-between; padding: clamp(22px, 6vh, 62px) 8% 34px 30%; background: linear-gradient(90deg, rgba(255,255,255,.08), rgba(255,255,255,.64) 33%, rgba(255,255,255,.75) 100%), linear-gradient(0deg, rgba(6,37,31,.55), transparent 38%), url('/brand/city.jpg') center/cover no-repeat; }
  .story-copy .eyebrow { margin: 0 0 25px; color: #60746f; }
  h1 { max-width: 650px; margin: 0; font: 500 clamp(30px, 2.9vw, 49px)/1.18 'Lora', Georgia, serif; letter-spacing: -.055em; color: #0b3030; }
  .story-copy > p:last-child { max-width: 530px; margin: 25px 0 0; font: 15px/1.75 'Lora', Georgia, serif; color: #50605b; }
  .image-caption { width: fit-content; margin: 0; color: white; font: 15px/1.6 'Lora', Georgia, serif; text-shadow: 0 1px 10px #183f38; }
  .image-caption::before { display: block; content: ''; width: 42px; height: 1px; margin-bottom: 16px; background: white; }
  .auth-panel { min-width: 0; min-height: 0; display: flex; flex-direction: column; justify-content: center; margin: 0 5% 0 0; padding: clamp(18px, 3vh, 38px) clamp(24px, 3vw, 45px); border-radius: 18px 18px 0 0; background: rgba(255,255,255,.90); box-shadow: -18px 0 52px rgba(26,59,52,.08); }
  .auth-panel .eyebrow { margin: 0 0 6px; }
  h2 { margin: 0; font: 500 clamp(42px, 3.5vw, 61px)/1.1 'Lora', Georgia, serif; letter-spacing: -.065em; color: #0d3431; }
  .panel-intro { margin: 10px 0 28px; color: #65736d; font: 15px/1.55 'Lora', Georgia, serif; }
  .auth-form { display: grid; gap: 10px; }
  label { margin-top: 7px; font: 600 13px 'Lora', Georgia, serif; color: #193d3a; }
  .input-wrap { display: flex; align-items: center; gap: 12px; height: 47px; padding: 0 14px; border: 1px solid #dbe4e0; border-radius: 6px; color: #325b55; background: #fff; }
  .input-wrap:focus-within { border-color: #2c7569; box-shadow: 0 0 0 3px #dfefea; }
  input { flex: 1; width: 0; border: 0; outline: 0; color: #163b35; background: transparent; font-size: 12px; }
  input::placeholder { color: #9aa9a4; }
  .toggle-password { display: grid; place-items: center; border: 0; background: transparent; color: #45645f; }
  .submit, .register-link { height: 48px; display: flex; align-items: center; justify-content: center; gap: 12px; border-radius: 99px; font-weight: 600; font-size: 13px; }
  .submit { margin-top: 18px; border: 0; color: #fff; background: #1e5b54; }
  .submit:hover { background: #103f3a; }
  .or { position: relative; margin: 20px 0; text-align: center; color: #9ca9a5; font: 13px 'Lora', Georgia, serif; }
  .or::before { content: ''; position: absolute; top: 50%; left: 0; width: 100%; height: 1px; background: #e2e9e5; }
  .or span { position: relative; padding: 0 15px; background: white; }
  .register-link { border: 1px solid #28665d; color: #174a43; }
  .register-link:hover { background: #edf6f3; }
  .values { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; margin-top: 28px; padding: 20px 10px; border-radius: 10px; background: #f3f7f5; }
  .values > div { display: grid; align-content: start; gap: 7px; padding: 0 13px; border-right: 1px solid #dce5e1; }
  .values > div:last-child { border: 0; }
  .values :global(svg) { color: #1e5b54; }
  .values strong { font: 600 11px/1.25 'Lora', Georgia, serif; }
  .values span { color: #657a74; font: 10px/1.5 'Lora', Georgia, serif; }
  .auth-footnote { margin: 22px 0 0; color: #869591; text-align: right; font: italic 11px 'Lora', Georgia, serif; }
  .form-error { margin: 0; color: #a63d43; font-size: 12px; }
  @media (min-width: 961px) and (max-height: 850px) { .auth-panel { padding-top: 18px; padding-bottom: 18px; } .panel-intro { margin-bottom: 18px; } .values, .auth-footnote { display: none; } .story-copy > p:last-child { margin-top: 18px; } }
  @media (min-width: 961px) and (max-height: 650px) { .auth-header { gap: 16px; } .auth-story { padding-bottom: 18px; } .story-copy > p:last-child, .image-caption { display: none; } .auth-panel { padding-top: 10px; padding-bottom: 10px; } .panel-intro { margin-bottom: 10px; font-size: 13px; } .auth-form { gap: 6px; } label { margin-top: 2px; } .submit { margin-top: 8px; } .or { margin: 12px 0; } }
  @media (max-width: 1100px) { .auth-story { padding-left: 15%; } .auth-content { grid-template-columns: 51% 49%; } .auth-header { padding: 0 28px; } .auth-panel { padding: 32px; margin-right: 0; } }
  @media (max-width: 960px) { .auth-backdrop { display: block; height: auto; min-height: 100vh; min-height: 100dvh; overflow: visible; padding: 0; } .auth-frame { display: block; height: auto; min-height: 100vh; min-height: 100dvh; overflow: visible; border: 0; border-radius: 0; } .auth-header { height: 66px; padding: 0 20px; } .auth-header :global(.brand-logo) { --mark-size: 29px !important; } .brand-divider, .tagline, .auth-header-right { display: none; } .auth-content { display: flex; flex-direction: column; } .auth-story { min-height: 245px; padding: 38px 24px 22px; background-position: center 62%; } .story-copy .eyebrow { margin-bottom: 12px; color: #ebf4ef; text-shadow: 0 1px 5px #16453e; } h1 { max-width: 430px; color: white; font-size: clamp(27px, 7vw, 38px); text-shadow: 0 2px 9px #123c36; } .story-copy > p:last-child, .image-caption { display: none; } .auth-panel { position: relative; display: block; margin: -16px 0 0; padding: 32px 24px 26px; border-radius: 18px 18px 0 0; } .panel-intro { margin-bottom: 22px; } .values { padding: 16px 5px; } .values > div { padding: 0 8px; } }
  @media (max-width: 420px) { .values span { display: none; } .values { margin-top: 23px; } }
</style>
