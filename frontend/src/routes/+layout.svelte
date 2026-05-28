<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import '../app.css';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import Toast from '$lib/apple-glass/components/Toast.svelte';
  import NotificationBell from '$lib/components/NotificationBell.svelte';
  import { user } from '$lib/stores/auth';
  import { notifications } from '$lib/stores/notifications';
  import { clearToast, toast } from '$lib/stores/toast';
  export let data: { user: import('$lib/types').User | null };
  $: user.set(data.user);

  const topicColors = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
  const topicLabels: Record<string, string> = {
    tech: 'Công nghệ', science: 'Khoa học', sports: 'Thể thao',
    politics: 'Chính trị', entertainment: 'Giải trí', health: 'Sức khoẻ',
    business: 'Kinh doanh', culture: 'Văn hoá', education: 'Giáo dục',
    environment: 'Môi trường', ai: 'Trí tuệ nhân tạo', news: 'Tin tức',
  };

  let theme: 'light' | 'dark' = 'light';
  let q = '';

  function handleSearch() {
    const trimmed = q.trim();
    if (trimmed) goto(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  $: pathname = $page.url.pathname as string;
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
            : pathname.startsWith('/settings')
              ? 'Cài đặt'
              : 'Oecophylla';
  $: activeNav =
    pathname === '/'
      ? 'feed'
      : pathname.startsWith('/search')
        ? 'search'
        : pathname.startsWith('/profile/')
          ? 'profile'
          : pathname.startsWith('/admin')
            ? 'admin'
            : pathname.startsWith('/settings')
              ? 'settings'
              : pathname.startsWith('/notifications')
                ? 'notifications'
                : pathname === '/saved'
                  ? 'saved'
                  : pathname.startsWith('/post/')
                    ? 'feed'
                    : 'feed';
  $: mobileNavActive =
    pathname === '/'
      ? 'home'
      : pathname.startsWith('/search')
        ? 'search'
        : pathname.startsWith('/post/new')
          ? 'write'
          : pathname.startsWith('/notifications')
            ? 'notifications'
            : pathname.startsWith('/profile/')
              ? 'profile'
              : pathname === '/saved'
                ? 'saved'
                : pathname.startsWith('/admin')
                  ? 'admin'
                  : '';

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
        <a class:active={activeNav === 'feed' && $page.url.searchParams.get('feed') !== 'following'} class="nav-item" href="/">
          <Icon name="Home" size={18} />
          <span>Trang chủ</span>
        </a>
        <a class:active={activeNav === 'search'} class="nav-item" href="/search">
          <Icon name="Compass" size={18} />
          <span>Khám phá</span>
        </a>
        <a class:active={pathname === '/' && $page.url.searchParams.get('feed') === 'following'} class="nav-item" href="/?feed=following">
          <Icon name="Users" size={18} />
          <span>Theo dõi</span>
        </a>
        <a class:active={activeNav === 'saved'} class="nav-item" href="/saved">
          <Icon name="Bookmark" size={18} />
          <span>Đã lưu</span>
        </a>
        <a class:active={activeNav === 'notifications'} class="nav-item" href="/notifications">
          <Icon name="Bell" size={18} />
          <span>Thông báo</span>
          {#if $notifications.unread > 0}
            <span class="nav-badge">{$notifications.unread > 99 ? '99+' : $notifications.unread}</span>
          {/if}
        </a>
        <a class:active={activeNav === 'profile'} class="nav-item" href={profileHref}>
          <Icon name="User" size={18} />
          <span>Hồ sơ</span>
        </a>
        {#if currentUser?.role === 'admin'}
          <a class:active={activeNav === 'admin'} class="nav-item" href="/admin">
            <Icon name="Shield" size={18} />
            <span>Quản trị</span>
          </a>
        {/if}
      </nav>

      {#if currentUser?.topic_prefs?.length}
        <div class="nav-section">Của bạn</div>
        <nav class="nav">
          {#each (currentUser.topic_prefs ?? []).slice(0, 4) as topic, i}
            <a class="nav-item" href="/search?q={encodeURIComponent(topic)}">
              <span class="topic-dot" style="background:{topicColors[i % topicColors.length]};width:10px;height:10px;border-radius:50%;flex-shrink:0;display:inline-block;"></span>
              <span>{topicLabels[topic] ?? topic}</span>
            </a>
          {/each}
        </nav>
      {/if}

      <div class="sidebar-foot">
        {#if currentUser}
          <div class="profile-card">
            <a href={profileHref} style="display:contents">
              <div class="brand-mark" style="width: 36px; height: 36px; border-radius: 12px; flex-shrink:0;">
                {(currentUser.display_name ?? currentUser.username).slice(0, 1).toUpperCase()}
              </div>
              <div style="min-width: 0; flex: 1">
                <div class="name">{currentUser.display_name ?? currentUser.username}</div>
                <div class="handle">@{currentUser.username}</div>
              </div>
            </a>
            <a href="/settings" class="muted" title="Cài đặt" style="display:flex;align-items:center;padding:4px;">
              <Icon name="Settings" size={16} />
            </a>
          </div>
          <form action="/logout" method="post" style="margin-top:4px;">
            <button class="nav-item" type="submit" style="width:100%;font-size:12px;opacity:0.6;">
              <Icon name="ArrowLeft" size={14} />
              <span>Đăng xuất</span>
            </button>
          </form>
        {:else}
          <div class="profile-card">
            <div style="min-width: 0; flex: 1">
              <div class="name">Khách</div>
              <div class="handle">Đăng nhập để cá nhân hoá bảng tin</div>
            </div>
          </div>
          <div style="display:flex;gap:8px;margin-top:8px;">
            <a class="nav-item" href="/login" style="flex:1;font-size:12px;">
              <Icon name="ArrowRight" size={14} />
              <span>Đăng nhập</span>
            </a>
            <a class="nav-item" href="/register" style="flex:1;font-size:12px;">
              <Icon name="Plus" size={14} />
              <span>Tạo tài khoản</span>
            </a>
          </div>
        {/if}
      </div>
    </aside>

    <div>
      <header class="topbar">
        <div class="crumbs" data-testid={pathname === '/' ? 'feed-heading' : undefined}>{@html crumbs}</div>
        <form class="search" on:submit|preventDefault={handleSearch}>
          <span class="icon"><Icon name="Search" size={15} /></span>
          <input bind:value={q} placeholder="Tìm chủ đề, tác giả, hoặc bài viết…" />
        </form>
        <div class="topbar-actions">
          {#if currentUser?.role === 'admin'}
            <a class="btn ghost sm" href="/admin">
              <Icon name="Shield" size={14} /> Khu vực quản trị
            </a>
          {/if}
          <button class="icon-btn" title="Đổi giao diện" on:click={() => (theme = theme === 'dark' ? 'light' : 'dark')}>
            <Icon name={theme === 'dark' ? 'Sun' : 'Moon'} size={18} />
          </button>
          <NotificationBell enabled={Boolean(currentUser)} />
        </div>
      </header>

      <slot />
    </div>

    <!-- Mobile bottom navigation (hidden — Apple Glass reference uses icon-strip sidebar instead) -->
    {#if false}
    <nav class="mobile-nav">
      <a class:active={mobileNavActive === 'home'} class="mobile-nav-item" href="/">
        <Icon name="Home" size={20} />
        <span>Trang chủ</span>
      </a>
      <a class:active={mobileNavActive === 'search'} class="mobile-nav-item" href="/search">
        <Icon name="Compass" size={20} />
        <span>Khám phá</span>
      </a>
      <a class:active={mobileNavActive === 'write'} class="mobile-nav-item" href="/post/new">
        <Icon name="Edit" size={20} />
        <span>Viết bài</span>
      </a>
      <a class:active={mobileNavActive === 'notifications'} class="mobile-nav-item" href="/notifications">
        <div class="relative">
          <Icon name="Bell" size={20} />
          {#if $notifications.unread > 0}
            <span class="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold flex items-center justify-center">
              {$notifications.unread > 99 ? '99+' : $notifications.unread}
            </span>
          {/if}
        </div>
        <span>Thông báo</span>
      </a>
      <a class:active={mobileNavActive === 'profile'} class="mobile-nav-item" href={profileHref}>
        <Icon name="User" size={20} />
        <span>Hồ sơ</span>
      </a>
    </nav>
    {/if}
  </div>
{:else}
  <slot />
{/if}

{#if $toast}
  <Toast message={$toast.message} onClose={clearToast} />
{/if}
