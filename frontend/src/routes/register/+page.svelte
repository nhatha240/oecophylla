<script lang="ts">
  import Logo from '$lib/components/Logo.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let form: { error?: string } | null = null;
  let showPassword = false;
</script>

<svelte:head><title>Tạo tài khoản — Oecophylla</title></svelte:head>

<main class="register-layout">
  <section class="register-story">
    <a href="/" aria-label="Trang chủ Oecophylla"><Logo size={40} /></a>
    <div><p class="eyebrow">CỘNG ĐỒNG · KẾT NỐI · CÙNG PHÁT TRIỂN</p><h1 class="serif">Những cuộc đối thoại tốt đẹp hơn, cho một Việt Nam hiểu sâu hơn.</h1><p>Đọc những nguồn tin đáng tin cậy, chia sẻ suy nghĩ của bạn và đồng hành cùng cộng đồng tử tế.</p></div>
    <small>Tri thức kết nối con người. — Oecophylla</small>
  </section>
  <section class="register-panel" aria-labelledby="register-title">
    <div class="mobile-brand"><a href="/" aria-label="Trang chủ Oecophylla"><Logo size={32} /></a></div>
    <p class="eyebrow">CHÀO MỪNG BẠN ĐẾN VỚI</p><h2 class="serif" id="register-title">Tạo tài khoản</h2><p class="intro">Gia nhập cộng đồng Oecophylla để đọc, thảo luận và cùng kiến tạo những giá trị tích cực.</p>
    <form method="POST">
      <label for="display_name">Họ và tên</label><div class="field"><label class="field-target" for="display_name"><Icon name="User" size={18} /><input id="display_name" name="display_name" autocomplete="name" placeholder="Nhập họ và tên" maxlength="100" /></label></div>
      <label for="username">Tên người dùng</label><div class="field"><label class="field-target" for="username"><Icon name="User" size={18} /><input id="username" name="username" autocomplete="username" pattern={'[a-z0-9_]{3,30}'} title="3–30 ký tự: chữ thường, số hoặc dấu gạch dưới" placeholder="tennguoidung" required /></label></div>
      <label for="email">Email</label><div class="field"><label class="field-target" for="email"><Icon name="Link" size={18} /><input id="email" name="email" type="email" autocomplete="email" placeholder="ban@vidu.com" required /></label></div>
      <label for="password">Mật khẩu</label><div class="field"><label class="field-target" for="password"><Icon name="Shield" size={18} /><input id="password" name="password" type={showPassword ? 'text' : 'password'} autocomplete="new-password" minlength="8" maxlength="128" placeholder="Tạo mật khẩu" required /></label><button type="button" aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} on:click={() => showPassword = !showPassword}><Icon name={showPassword ? 'EyeOff' : 'Eye'} size={17} /></button></div>
      <p class="hint">Tối thiểu 8 ký tự. Hãy chọn mật khẩu khó đoán.</p>
      {#if form?.error}<p class="error" role="alert">{form.error}</p>{/if}
      <button type="submit" class="submit">Đăng ký <Icon name="ArrowRight" size={18} /></button>
    </form>
    <p class="signin">Đã có tài khoản? <a href="/login">Đăng nhập</a></p>
  </section>
</main>

<style>
  .register-layout { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); width: 100%; height: 100vh; height: 100dvh; min-height: 0; margin: 0; overflow: hidden; border: 0; border-radius: 0; background: white; box-shadow: none; }
  .register-story { min-width: 0; min-height: 0; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; padding: 40px 55px; background: linear-gradient(0deg, #092f2eaa, transparent 65%), linear-gradient(90deg, #ffffffd9, #ffffff36), url('/brand/city.jpg') center/cover; }
  .register-story > div { max-width: 540px; margin-top: 80px; }
  .register-story h1 { margin: 15px 0 20px; color: #0b3533; font-size: clamp(32px, 3.3vw, 52px); line-height: 1.2; letter-spacing: -.055em; font-weight: 500; }
  .register-story div > p:last-child { max-width: 480px; font: 16px/1.7 'Lora', serif; }
  .register-story small { color: white; font: italic 14px 'Lora', serif; }
  .register-panel { min-width: 0; min-height: 0; display: flex; flex-direction: column; align-self: stretch; width: min(100%, 520px); margin: 0 auto; padding: clamp(20px, 4vh, 45px) 55px; overflow: hidden; }
  .mobile-brand { display: none; }
  h2 { margin: 5px 0 10px; font-size: 36px; font-weight: 500; letter-spacing: -.05em; }
  .intro { margin: 0 0 28px; color: #71817b; font: 14px/1.6 'Lora', serif; }
  form { min-height: 0; flex: 1; display: grid; align-content: start; gap: 9px; overflow-y: auto; overflow-x: hidden; overscroll-behavior: contain; padding-right: 4px; }
  label { margin-top: 11px; font: 600 13px 'Lora', serif; }
  .field { display: flex; align-items: center; height: 46px; border: 1px solid #dfe8e3; border-radius: 7px; color: #43675f; }
  .field:focus-within { border-color: #1d675b; box-shadow: 0 0 0 3px rgba(29,103,91,.22); }
  .field-target { display: flex; align-items: center; flex: 1; gap: 10px; min-width: 0; height: 100%; margin: 0; padding: 0 13px; font: inherit; cursor: text; }
  input { flex: 1; width: 0; height: 100%; border: 0; outline: 0; background: transparent; font-size: 12px; }
  input::placeholder { color: #a2afa9; }
  .field button { display: grid; place-items: center; flex: 0 0 32px; height: 32px; margin-right: 6px; border: 0; background: transparent; color: #42675f; }
  .hint { margin: 0; color: #879891; font-size: 10px; }
  .error { margin: 0; color: #ad4144; font-size: 12px; }
  .submit { display: flex; justify-content: center; align-items: center; gap: 10px; height: 48px; margin-top: 15px; border: 0; border-radius: 99px; color: white; background: #1d5b54; font-weight: 600; }
  .submit:hover { background: #104139; }
  .signin { flex: 0 0 auto; margin: 18px 0 0; color: #758780; text-align: center; font: 13px 'Lora', serif; }
  .signin a { color: #1d5b54; text-decoration: underline; }
  @media (min-width: 851px) and (max-height: 650px) { .register-story { padding: 24px 36px; } .register-story > div { margin-top: 20px; } .register-story h1 { font-size: clamp(28px, 3vw, 40px); } .register-story div > p:last-child { display: none; } .register-panel { padding-top: 20px; padding-bottom: 20px; } .intro { margin-bottom: 14px; } }
  @media (max-width: 850px) { .register-layout { grid-template-columns: 1fr; width: 100%; height: auto; min-height: 100vh; min-height: 100dvh; margin: 0; overflow: visible; border: 0; border-radius: 0; } .register-story { display: none; } .register-panel { display: block; align-self: center; margin: auto; padding: 28px 24px; overflow: visible; } form { display: grid; overflow: visible; padding-right: 0; } .mobile-brand { display: block; margin-bottom: 38px; } }
</style>
