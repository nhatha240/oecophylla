<script lang="ts">
  import Icon from './Icon.svelte';

  export let crumbs = '';
  export let search = true;
  export let theme = 'light';
  export let onTheme: () => void = () => {};
  export let onAdmin: (() => void) | null = null;
  export let onNotif: () => void = () => {};
</script>

<header class="topbar">
  {#if crumbs}
    <div class="crumbs">{@html crumbs}</div>
  {/if}
  {#if search}
    <div class="search">
      <span class="icon"><Icon name="Search" size={15} /></span>
      <input placeholder="Tìm chủ đề, tác giả, hoặc bài viết…" />
    </div>
  {/if}
  <div class="topbar-actions">
    <slot name="right" />
    <button class="icon-btn" title="Đổi giao diện" on:click={onTheme}>
      <Icon name={theme === 'dark' ? 'Sun' : 'Moon'} size={18} />
    </button>
    <button class="icon-btn" title="Trung tâm thông báo" on:click={onNotif} data-notif-trigger>
      <Icon name="Bell" size={18} />
      <span class="dot"></span>
    </button>
    {#if onAdmin}
      <button class="btn ghost sm" on:click={onAdmin} style="margin-left: 6px">
        <Icon name="Shield" size={14} /> Khu vực quản trị
      </button>
    {/if}
  </div>
</header>
