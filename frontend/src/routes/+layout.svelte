<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import '../app.css';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { user } from '$lib/stores/auth';
  export let data: { user: import('$lib/types').User | null };
  $: user.set(data.user);

  let theme: 'light' | 'dark' = 'light';

  $: pathname = $page.url.pathname;
  $: isAuthRoute = pathname === '/login' || pathname === '/register';
  $: isAdminRoute = pathname.startsWith('/admin');
  $: useShell = !isAuthRoute && !isAdminRoute;
  $: currentUser = data.user;
  $: profileHref = currentUser ? `/profile/${currentUser.id}` : '/login';
  $: crumbs =
    pathname === '/'
      ? 'Bảng tin <em>· Dành cho bạn</em>'
      : pathname.startsWith('/post/new')
        ? 'Soạn bài viết'
        : pathname.startsWith('/post/')
          ? 'Bài viết <em>· chi tiết</em>'
          : pathname.startsWith('/profile/')
            ? 'Hồ sơ'
            : 'Oecophylla';
  $: activeNav =
    pathname === '/'
      ? 'feed'
      : pathname.startsWith('/profile/')
        ? 'profile'
        : pathname.startsWith('/admin')
          ? 'admin'
          : pathname.startsWith('/post/')
            ? 'feed'
            : 'feed';

  onMount(() => {
    const saved = window.localStorage.getItem('oec-theme');
    if (saved === 'dark' || saved === 'light') theme = saved;
  });

  $: if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme);
    window.localStorage.setItem('oec-theme', theme);
  }
</script>

{#if useShell}
  <div class="app">
    <aside class="sidebar">
      <a class="brand" href="/">
        <div class="brand-mark">O</div>
        <div class="brand-name">Oecophy<em>lla</em></div>
      </a>

      <nav class="nav">
        <a class:active={activeNav === 'feed'} class="nav-item" href="/">
          <Icon name="Home" size={18} />
          <span>Trang chủ</span>
        </a>
        <a class="nav-item" href="/">
          <Icon name="Compass" size={18} />
          <span>Khám phá</span>
        </a>
        <a class="nav-item" href="/">
          <Icon name="Users" size={18} />
          <span>Đang theo dõi</span>
        </a>
        <a class="nav-item" href="/post/new">
          <Icon name="Edit" size={18} />
          <span>Viết bài</span>
        </a>
        <a class="nav-item" href="/">
          <Icon name="Bookmark" size={18} />
          <span>Đã lưu</span>
        </a>
        <a class:active={activeNav === 'profile'} class="nav-item" href={profileHref}>
          <Icon name="User" size={18} />
          <span>Hồ sơ</span>
        </a>

        <div class="nav-section">Tài khoản</div>
        {#if currentUser}
          {#if currentUser.role === 'admin'}
            <a class="nav-item" href="/admin">
              <Icon name="Shield" size={18} />
              <span>Quản trị</span>
            </a>
          {/if}
          <form action="/logout" method="post">
            <button class="nav-item" type="submit">
              <Icon name="ArrowLeft" size={18} />
              <span>Đăng xuất</span>
            </button>
          </form>
        {:else}
          <a class="nav-item" href="/login">
            <Icon name="ArrowRight" size={18} />
            <span>Đăng nhập</span>
          </a>
          <a class="nav-item" href="/register">
            <Icon name="Plus" size={18} />
            <span>Tạo tài khoản</span>
          </a>
        {/if}
      </nav>

      <div class="sidebar-foot">
        {#if currentUser}
          <a class="profile-card" href={profileHref}>
            <div class="brand-mark" style="width: 36px; height: 36px; border-radius: 12px;">
              {(currentUser.display_name ?? currentUser.username).slice(0, 1).toUpperCase()}
            </div>
            <div style="min-width: 0; flex: 1">
              <div class="name">{currentUser.display_name ?? currentUser.username}</div>
              <div class="handle">@{currentUser.username}</div>
            </div>
            <Icon name="Settings" size={16} className="muted" />
          </a>
        {:else}
          <div class="profile-card">
            <div style="min-width: 0; flex: 1">
              <div class="name">Khách</div>
              <div class="handle">Đăng nhập để cá nhân hoá bảng tin</div>
            </div>
          </div>
        {/if}
      </div>
    </aside>

    <div>
      <header class="topbar">
        <div class="crumbs">{@html crumbs}</div>
        <div class="search">
          <span class="icon"><Icon name="Search" size={15} /></span>
          <input placeholder="Tìm chủ đề, tác giả, hoặc bài viết…" />
        </div>
        <div class="topbar-actions">
          {#if currentUser?.role === 'admin'}
            <a class="btn ghost sm" href="/admin">
              <Icon name="Shield" size={14} /> Khu vực quản trị
            </a>
          {/if}
          <button class="icon-btn" title="Đổi giao diện" on:click={() => (theme = theme === 'dark' ? 'light' : 'dark')}>
            <Icon name={theme === 'dark' ? 'Sun' : 'Moon'} size={18} />
          </button>
          <button class="icon-btn" title="Thông báo">
            <Icon name="Bell" size={18} />
          </button>
        </div>
      </header>

      <slot />
    </div>
  </div>
{:else}
  <slot />
{/if}
