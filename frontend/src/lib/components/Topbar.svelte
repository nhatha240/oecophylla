<script lang="ts">
  import { user } from '$lib/stores/auth';
</script>
<header class="sticky top-3 mx-auto max-w-3xl glass-surface flex items-center justify-between px-5 py-3 mt-3">
  <a href="/" class="text-display-serif text-2xl">Oecophylla</a>
  <nav class="flex items-center gap-2">
    {#if $user}
      <a class="glass-chip" href="/profile/{$user.id}">{$user.display_name ?? $user.username}</a>
      <form method="post" action="/logout"><button class="glass-pill" type="submit">Đăng xuất</button></form>
    {:else}
      <a class="glass-chip" href="/login">Đăng nhập</a>
      <a class="glass-button-primary" href="/register">Đăng ký</a>
    {/if}
  </nav>
</header>
