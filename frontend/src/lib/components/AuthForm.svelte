<script lang="ts">
  export let mode: 'login' | 'register';
  export let error: string | null = null;
</script>
<section class="glass-surface p-6 mt-8 max-w-md mx-auto">
  <h1 class="text-display-serif text-3xl mb-4">{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1>
  <form method="post" class="flex flex-col gap-3">
    {#if mode === 'register'}
      <label class="text-sm">Username
        <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name="username" required />
      </label>
      <label class="text-sm">Tên hiển thị
        <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name="display_name" />
      </label>
    {/if}
    <label class="text-sm">{mode === 'login' ? 'Email hoặc username' : 'Email'}
      <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" name={mode === 'login' ? 'email_or_username' : 'email'} required />
    </label>
    <label class="text-sm">Mật khẩu
      <input class="block w-full mt-1 px-3 py-2 rounded-xl bg-white/60 border border-white/60" type="password" name="password" required />
    </label>
    {#if error}<p class="text-red-700 text-sm">{error}</p>{/if}
    <button class="glass-button-primary mt-2" type="submit">{mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}</button>
  </form>
</section>
