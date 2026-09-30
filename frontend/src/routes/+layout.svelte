<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import type { User } from '$lib/types';
  import { user } from '$lib/stores/auth';
  import Logo from '$lib/components/Logo.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import '../app.css';

  export let data: { user: User | null };
  let query = '';
  $: if (browser) user.set(data.user);
  $: path = $page.url.pathname as string;
  $: authPage = path === '/login' || path === '/register';
  $: profileHref = data.user ? '/profile/' + data.user.id : '/login';
  function submitSearch() { if (query.trim()) goto('/search?q=' + encodeURIComponent(query.trim())); }
</script>

{#if authPage}
  <slot />
{:else}
  <div class="oec-shell">
    <header class="oec-header">
      <a href="/" class="brand-link" aria-label="Oecophylla - Trang chủ"><Logo size={34} /></a>
      <form class="header-search" on:submit|preventDefault={submitSearch} role="search">
        <Icon name="Search" size={17} />
        <input aria-label="Tìm kiếm" bind:value={query} placeholder="Tìm kiếm tin tức, chủ đề, người dùng..." />
      </form>
      <span class="header-spacer"></span>
      <a href="/post/new" class="header-action"><Icon name="Edit" size={17} /> Viết bài</a>
      <a href="/notifications" class="header-icon" aria-label="Thông báo"><Icon name="Bell" size={21} /></a>
      <details class="user-menu"><summary class="header-user">
        {#if data.user?.avatar_url}<img src={data.user.avatar_url} alt="" />{:else}<span class="initials">{(data.user?.display_name ?? data.user?.username ?? 'O').slice(0, 1).toUpperCase()}</span>{/if}
        <span>{data.user?.display_name ?? data.user?.username ?? 'Tài khoản'}</span>
        <Icon name="Chevron" size={13} />
      </summary><div class="user-menu-panel"><a href={profileHref}>Hồ sơ của tôi</a><a href="/my-posts">Bài viết của tôi</a><a href="/settings">Cài đặt</a><form method="POST" action="/logout"><button type="submit">Đăng xuất</button></form></div></details>
    </header>
    <div class="oec-body">
      <aside class="oec-sidebar" aria-label="Điều hướng chính">
        <nav class="side-nav">
          <a class:active={path === '/' && $page.url.searchParams.get('feed') !== 'following'} href="/"><Icon name="Home" size={17} /> Trang chủ</a>
          <a class:active={path === '/search'} href="/search"><Icon name="Compass" size={17} /> Khám phá</a>
          <a class:active={path === '/' && $page.url.searchParams.get('feed') === 'following'} href="/?feed=following"><Icon name="Users" size={17} /> Đang theo dõi</a>
          <a class:active={path === '/notifications'} href="/notifications"><Icon name="Bell" size={17} /> Thông báo</a>
          <a class:active={path === '/saved'} href="/saved"><Icon name="Bookmark" size={17} /> Bài đã lưu</a>
          <a class:active={path === '/my-posts'} href="/my-posts"><Icon name="FileText" size={17} /> Bài viết của tôi</a>
          <a class:active={path.startsWith('/profile/')} href={profileHref}><Icon name="User" size={17} /> Hồ sơ</a>
          {#if data.user?.role === 'admin'}<a class:active={path.startsWith('/admin')} href="/admin"><Icon name="Shield" size={17} /> Quản trị</a>{/if}
        </nav>
        <p class="side-label">Chủ đề yêu thích</p>
        <nav class="side-nav">
          <a href="/search?q=Thời sự"><Icon name="Globe" size={16} /> Thời sự</a>
          <a href="/search?q=Kinh tế"><Icon name="ChartBar" size={16} /> Kinh tế</a>
          <a href="/search?q=Khoa học"><Icon name="Atom" size={16} /> Khoa học</a>
          <a href="/search?q=Môi trường"><Icon name="Heart" size={16} /> Môi trường</a>
          <a href="/search?q=Công nghệ"><Icon name="Cpu" size={16} /> Công nghệ</a>
          <a href="/search?q=Giáo dục"><Icon name="Book" size={16} /> Giáo dục</a>
        </nav>
        <p class="sidebar-quote">“Những cuộc đối thoại tốt đẹp hơn, tạo nên thế giới tốt đẹp hơn.”<span>— Oecophylla</span></p>
      </aside>
      <main class="oec-main"><slot /></main>
    </div>
  </div>
  <nav class="mobile-nav" aria-label="Điều hướng di động">
    <a class:active={path === '/'} href="/"><Icon name="Home" size={20} />Trang chủ</a>
    <a class:active={path === '/search'} href="/search"><Icon name="Compass" size={20} />Khám phá</a>
    <a class="mobile-plus" href="/post/new" aria-label="Viết bài"><Icon name="Plus" size={23} /></a>
    <a class:active={path === '/notifications'} href="/notifications"><Icon name="Bell" size={20} />Thông báo</a>
    <a class:active={path.startsWith('/profile/')} href={profileHref}><Icon name="User" size={20} />Hồ sơ</a>
  </nav>
{/if}
